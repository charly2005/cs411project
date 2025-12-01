# ------------------------------------------------------------
# CareRoute Desktop Application
# PySide6 GUI application that:
#  - Accepts symptom text, optional vitals, and user location
#  - Calls Gemini API for triage classification
#  - Applies safety-layer rules to ensure reliability
#  - Recommends nearby facilities based on urgency
#  - Stores and displays historical triage sessions ("My Data")
# ------------------------------------------------------------

import sys  # Standard library module for system-specific parameters and functions

from PySide6.QtWidgets import (  # Import Qt widgets used to build the UI
    QApplication,   # Core Qt application class
    QWidget,        # Base class for all UI windows
    QVBoxLayout,    # Vertical layout manager
    QHBoxLayout,    # Horizontal layout manager
    QLabel,         # Display non-editable text
    QLineEdit,      # Single-line text input
    QCheckBox,      # Check box input widget
    QPushButton,    # Clickable button widget
    QMessageBox,    # Standard dialog for alerts and messages
    QStackedWidget, # Widget that manages multiple pages stacked on top of each other
    QScrollArea,    # Scrollable area widget
    QFrame,         # Generic container widget for grouping content
    QSizePolicy,    # Controls how widgets grow/shrink with layouts
)
from PySide6.QtCore import Qt  # Core non-GUI functionality, including alignment flags and cursors

from models import Vitals, SymptomInput, TriageDecision  # Custom dataclasses for vitals, symptom input, and triage decision
from triage_engine import call_gemini_for_triage, apply_rule_safety_layer  # Functions to call Gemini and apply safety rules
from facilities_google import recommend_facilities  # Function to recommend facilities based on triage decision and location
from history import append_record, load_history  # Functions for persisting and loading triage history
from geolocation import geocode_address, GeocodingError  # Geocoding helper and custom error type


def urgency_to_score(urgency: str) -> int:
    """Map urgency level to numeric score 1-4.""" 
    u = (urgency or "").upper()  # Normalize urgency string to uppercase, handle None with default ""
    if u == "ER":  # If urgency is emergency room
        return 4  # Highest severity
    if u == "URGENT":  # If urgency is urgent care
        return 3  # Second highest severity
    if u == "CLINIC":  # If urgency is clinic / primary care
        return 2  # Medium severity
    return 1  # HOME / default severity for missing or low urgency levels


class MainWindow(QWidget):
    """Main application window for CareRoute Desktop.""" 

    def __init__(self):
        super().__init__()  # Initialize base QWidget

        self.setWindowTitle("CareRoute Desktop")  # Set the window title

        # Last resolved user location
        self.lat = None  # Latitude of user's address (float or None)
        self.lon = None  # Longitude of user's address (float or None)
        self.formatted_address = None  # Human-readable version of the resolved address

        # Last triage result
        self.last_symptoms_text = ""  # Stores last symptoms text shown on Result page
        self.current_decision = None  # Holds the last TriageDecision object
        self.current_recs = []  # List of facility recommendation results

        # Cached history records for "My Data" replay
        self.history_records = []  # In-memory storage of previously loaded history items

        self._build_shell()  # Build top-level shell layout, header, stacked pages, and disclaimer
        self._build_pages()  # Create individual pages and add them to the stacked widget

    # ------------------------------------------------------------------
    # Shell layout: header, stacked pages, footer disclaimer
    # ------------------------------------------------------------------
    def _build_shell(self):
        main_layout = QVBoxLayout(self)  # Main vertical layout for the entire window

        # ---------- Header (CareRoute + My Data + Home) ----------
        header_layout = QHBoxLayout()  # Horizontal layout for the header row

        # "My Data" folder button (top-left)
        self.my_data_button = QPushButton("📁  My Data")  # Button to open history page
        self.my_data_button.setCursor(Qt.PointingHandCursor)  # Use a pointing hand cursor on hover
        self.my_data_button.setStyleSheet(  # Apply custom styling for the button
            "QPushButton {"
            "  border: 2px solid #000;"
            "  border-radius: 12px;"
            "  padding: 8px 14px;"
            "  background: white;"
            "  font-size: 14px;"
            "}"
            "QPushButton:hover {"
            "  background: #f3f3f3;"
            "}"
        )
        self.my_data_button.clicked.connect(self.show_history_page)  # Clicking the button shows the History page
        header_layout.addWidget(self.my_data_button, alignment=Qt.AlignLeft)  # Add to header on the left

        # Title in the center
        title_layout = QVBoxLayout()  # Vertical layout for title and subtitle
        self.title_label = QLabel(  # Main title label with colored "CareRoute"
            "<span style='font-size:32px; font-weight:bold;'>"
            "<span style='color:#7FFFD4;'>Care</span>"
            "<span style='color:#00C0FF;'>Route</span>"
            "</span>"
        )
        self.title_label.setAlignment(Qt.AlignCenter)  # Center-align the title text

        subtitle = QLabel("AI-Powered Triage Engine")  # Subtitle label
        subtitle.setAlignment(Qt.AlignCenter)  # Center-align the subtitle
        subtitle.setStyleSheet("font-size:18px; font-weight:bold;")  # Style for subtitle text

        title_layout.addWidget(self.title_label)  # Add title to title layout
        title_layout.addWidget(subtitle)  # Add subtitle under title

        header_layout.addLayout(title_layout, stretch=1)  # Place title block in header, allowing it to stretch

        # Simple "Home" button on top-right for navigation
        self.home_button = QPushButton("Home")  # Button to navigate back to Home page
        self.home_button.setCursor(Qt.PointingHandCursor)  # Use pointing hand cursor
        self.home_button.setStyleSheet(  # Minimal styling to make it look like a text link
            "QPushButton { border: none; font-size: 14px; color: #007ACC; }"
            "QPushButton:hover { text-decoration: underline; }"
        )
        self.home_button.clicked.connect(self.show_home_page)  # Clicking the button shows the Home page
        header_layout.addWidget(self.home_button, alignment=Qt.AlignRight)  # Add Home button to right side of header

        main_layout.addLayout(header_layout)  # Add header to the top of the main layout

        # ---------- Stacked pages ----------
        self.stack = QStackedWidget()  # Widget that holds multiple pages, showing one at a time
        main_layout.addWidget(self.stack, stretch=1)  # Add stacked widget to main layout and allow it to expand

        # ---------- Disclaimer (bottom) ----------
        disclaimer = QLabel(  # Disclaimer label explaining the app is not a substitute for medical advice
            "The content on this application does not substitute medical advice. "
            "Always consult a licensed professional for personalized medical guidance."
        )
        disclaimer.setAlignment(Qt.AlignCenter)  # Center-align the disclaimer
        disclaimer.setWordWrap(True)  # Allow text wrapping for smaller window sizes
        disclaimer.setStyleSheet("font-size:10px; color:#555; margin-top:8px;")  # Subtle styling for disclaimer text
        main_layout.addWidget(disclaimer)  # Add disclaimer at the bottom of the main layout

    # ------------------------------------------------------------------
    # Build individual pages and add them to stacked widget
    # ------------------------------------------------------------------
    def _build_pages(self):
        self.home_page = self._build_home_page()    # Create Home page widget
        self.result_page = self._build_result_page()  # Create Result page widget
        self.history_page = self._build_history_page()  # Create History page widget

        self.stack.addWidget(self.home_page)    # index 0: Home page
        self.stack.addWidget(self.result_page)  # index 1: Result page
        self.stack.addWidget(self.history_page) # index 2: History page

        self.show_home_page()  # Set initial visible page to Home

    # ------------------------------------------------------------------
    # Page 1 – Home
    # ------------------------------------------------------------------
    def _build_home_page(self):
        page = QWidget()  # New widget that acts as the Home page
        layout = QVBoxLayout(page)  # Vertical layout for the Home page
        layout.setAlignment(Qt.AlignTop)  # Align content to the top

        layout.addSpacing(40)  # Add vertical spacing at the top

        # Top question title
        question = QLabel("What's bothering you today?")  # Prompt asking user about their symptoms
        question.setAlignment(Qt.AlignCenter)  # Center-align the question text
        question.setStyleSheet("font-size:28px; font-weight:bold;")  # Large, bold font for the question
        layout.addWidget(question)  # Add question label to layout

        layout.addSpacing(40)  # Add spacing between question and input row

        # --- Middle input row: [ large text box ] [ mic ] [ green arrow ] ---
        center_row = QHBoxLayout()  # Horizontal layout for main symptom input controls
        center_row.setAlignment(Qt.AlignCenter)  # Center the row as a whole

        self.symptoms_edit = QLineEdit()  # Input field for describing symptoms
        self.symptoms_edit.setPlaceholderText("Enter question here . . .")  # Placeholder text for input field
        self.symptoms_edit.setMinimumWidth(600)  # Set minimum width so it looks like a large search bar
        self.symptoms_edit.setMinimumHeight(54)  # Set minimum height for a pill-shaped input
        self.symptoms_edit.setStyleSheet(  # Rounded and styled line edit
            "QLineEdit {"
            "  font-size:16px;"
            "  padding: 10px 16px;"
            "  border-radius: 27px;"
            "  border: 2px solid #444;"
            "  background: white;"
            "}"
        )
        center_row.addWidget(self.symptoms_edit)  # Add symptom input to the center row

        # Mic icon (currently decorative only)
        mic_btn = QPushButton("🎤")  # Microphone emoji button as a visual element
        mic_btn.setEnabled(False)  # Disable functionality (not wired to audio input)
        mic_btn.setFixedSize(54, 54)  # Same height as text box for visual alignment
        mic_btn.setStyleSheet(  # Style to show as a circle-like button
            "QPushButton {"
            "  border-radius: 27px;"
            "  border: 2px solid #ccc;"
            "  background: #f2f2f2;"
            "  font-size:20px;"
            "}"
        )
        center_row.addSpacing(8)  # Small spacing between text box and mic button
        center_row.addWidget(mic_btn)  # Add mic button to the row

        # Green arrow button (triage trigger)
        self.triage_button = QPushButton("➜")  # Button that triggers the triage process
        self.triage_button.setCursor(Qt.PointingHandCursor)  # Use pointing hand cursor
        self.triage_button.setFixedSize(60, 60)  # Slightly larger button for emphasis
        self.triage_button.setStyleSheet(  # Dark background with bright green arrow
            "QPushButton {"
            "  border-radius: 30px;"
            "  background: black;"
            "  color: #A7FF4F;"
            "  font-size:28px;"
            "  font-weight:bold;"
            "}"
            "QPushButton:hover {"
            "  background: #222;"
            "}"
        )
        self.triage_button.clicked.connect(self.run_triage)  # Connect click event to triage workflow
        center_row.addSpacing(12)  # Add spacing between mic and arrow button
        center_row.addWidget(self.triage_button)  # Add arrow button to row

        layout.addLayout(center_row)  # Add the middle input row to the main layout

        layout.addSpacing(30)  # Spacing between main input and bottom panel

        # === Bottom panel: address + vitals, centered on the page ===
        bottom_panel = QFrame()  # Container frame for location and vitals
        bottom_panel.setStyleSheet("QFrame { background: transparent; }")  # No background color
        panel_layout = QVBoxLayout(bottom_panel)  # Vertical layout for bottom panel contents
        panel_layout.setAlignment(Qt.AlignTop)  # Align elements to top of panel
        panel_layout.setContentsMargins(0, 0, 0, 0)  # Remove default margins

        # --- Location row ---
        loc_layout = QHBoxLayout()  # Horizontal layout for address input and button
        loc_layout.setSpacing(10)  # Space between widgets in the row

        self.address_edit = QLineEdit()  # Input for user address or ZIP code
        self.address_edit.setPlaceholderText(  # Placeholder hint for user
            "Enter your address or ZIP code (required for nearby facilities)"
        )
        self.address_edit.setMinimumWidth(450)  # Reasonable minimum width
        self.address_edit.setStyleSheet(  # Subtle styling for smaller input
            "QLineEdit {"
            "  font-size:13px;"
            "  padding: 6px 10px;"
            "  border-radius: 18px;"
            "  border: 1px solid #bbb;"
            "  background: white;"
            "}"
        )
        loc_layout.addWidget(self.address_edit, stretch=3)  # Add address input to location row

        self.loc_button = QPushButton("Resolve Address")  # Button to trigger geocoding
        self.loc_button.setCursor(Qt.PointingHandCursor)  # Pointing hand cursor
        self.loc_button.setStyleSheet(  # Simple "pill" gray button
            "QPushButton {"
            "  padding: 6px 12px;"
            "  border-radius: 16px;"
            "  border: 1px solid #888;"
            "  background: #f7f7f7;"
            "  font-size:12px;"
            "}"
            "QPushButton:hover { background:#eee; }"
        )
        self.loc_button.clicked.connect(self.resolve_address)  # Connect click event to address resolver
        loc_layout.addWidget(self.loc_button)  # Add button to location row

        panel_layout.addLayout(loc_layout)  # Add location row to bottom panel

        # Label showing resolved address details
        self.loc_label = QLabel("Location: not set")  # Default location status
        self.loc_label.setWordWrap(True)  # Allow text wrapping
        self.loc_label.setStyleSheet("font-size:11px; color:#555; margin-top:4px;")  # Styling for location label
        panel_layout.addWidget(self.loc_label)  # Add location status label to panel

        panel_layout.addSpacing(10)  # Spacing between location and vitals

        # --- Vitals row ---
        vitals_layout = QHBoxLayout()  # Horizontal layout for vitals inputs
        vitals_layout.setSpacing(12)  # Space between vitals widgets

        self.temp_edit = QLineEdit()  # Input for temperature in °C
        self.temp_edit.setPlaceholderText("Temperature °C (optional)")  # Placeholder text
        self.temp_edit.setFixedWidth(200)  # Fixed width for uniform appearance
        self.temp_edit.setStyleSheet(  # Simple rounded style
            "QLineEdit {"
            "  font-size:12px;"
            "  padding: 4px 8px;"
            "  border-radius: 14px;"
            "  border: 1px solid #bbb;"
            "  background: white;"
            "}"
        )
        vitals_layout.addWidget(self.temp_edit)  # Add temperature input to vitals row

        self.pain_edit = QLineEdit()  # Input for pain score (0–10)
        self.pain_edit.setPlaceholderText("Pain 0-10 (optional)")  # Placeholder text
        self.pain_edit.setFixedWidth(200)  # Fixed width
        self.pain_edit.setStyleSheet(  # Styled similarly to temperature input
            "QLineEdit {"
            "  font-size:12px;"
            "  padding: 4px 8px;"
            "  border-radius: 14px;"
            "  border: 1px solid #bbb;"
            "  background: white;"
            "}"
        )
        vitals_layout.addWidget(self.pain_edit)  # Add pain score input

        self.pregnant_cb = QCheckBox("Pregnant")  # Checkbox for pregnancy status
        self.pregnant_cb.setStyleSheet("font-size:12px;")  # Smaller font for vitals checkbox
        vitals_layout.addWidget(self.pregnant_cb)  # Add pregnancy checkbox

        self.trauma_cb = QCheckBox("Recent trauma")  # Checkbox for recent trauma
        self.trauma_cb.setStyleSheet("font-size:12px;")  # Styling for trauma checkbox
        vitals_layout.addWidget(self.trauma_cb)  # Add trauma checkbox

        vitals_layout.addStretch(1)  # Push widgets to the left while filling row width
        panel_layout.addLayout(vitals_layout)  # Add vitals row to bottom panel

        # Center the bottom panel in the page
        layout.addWidget(bottom_panel, alignment=Qt.AlignHCenter)  # Add bottom panel to main layout, horizontally centered

        layout.addStretch(1)  # Push content to top by using extra stretch at bottom
        return page  # Return the completed Home page widget

    # ------------------------------------------------------------------
    # Page 2 – Result
    # ------------------------------------------------------------------
    def _build_result_page(self):
        page = QWidget()  # New widget for Result page
        layout = QHBoxLayout(page)  # Horizontal layout for Result page
        layout.setContentsMargins(40, 40, 40, 40)  # Add margins around the page content

        # ----- Left: big card -----
        card = QFrame()  # Frame for main result card
        card.setStyleSheet(  # Style card with border and rounded corners
            "QFrame {"
            "  background: white;"
            "  border-radius: 30px;"
            "  border: 4px solid #000;"
            "}"
        )
        card_layout = QVBoxLayout(card)  # Vertical layout inside the card
        card_layout.setContentsMargins(30, 30, 30, 30)  # Internal padding inside the card

        self.result_symptom_label = QLabel("I am feeling a small headache . . .")  # Label for summarized symptom text
        self.result_symptom_label.setStyleSheet("font-size:22px; font-weight:bold;")  # Make symptom summary prominent
        self.result_symptom_label.setWordWrap(True)  # Allow wrapping for long symptom descriptions
        card_layout.addWidget(self.result_symptom_label)  # Add symptom summary to card

        card_layout.addSpacing(10)  # Spacing between summary and score/explanation row

        # Score + explanation
        score_row = QHBoxLayout()  # Horizontal layout for score and explanation

        self.result_score_label = QLabel("1")  # Shows numeric severity score
        self.result_score_label.setStyleSheet(  # Large colored score number
            "font-size:72px; font-weight:bold; color:#88D840;"
        )
        score_row.addWidget(self.result_score_label, alignment=Qt.AlignTop)  # Place score at top of row

        self.result_explanation_label = QLabel("")  # Text block for the triage explanation
        self.result_explanation_label.setWordWrap(True)  # Allow explanation to wrap across multiple lines
        self.result_explanation_label.setStyleSheet("font-size:14px;")  # Normal-sized explanation font
        score_row.addWidget(self.result_explanation_label)  # Add explanation next to score

        card_layout.addLayout(score_row)  # Add score row to card

        card_layout.addSpacing(10)  # Spacing between score row and recommended action

        # Recommended action (stay home / clinic / urgent care / ER)
        self.result_destination_label = QLabel("")  # Label describing recommended next step
        self.result_destination_label.setWordWrap(True)  # Allow text wrapping
        self.result_destination_label.setStyleSheet("font-size:16px; font-weight:bold;")  # Slightly larger, bold text
        card_layout.addWidget(self.result_destination_label)  # Add recommended action label

        # Red flags line
        self.result_redflags_label = QLabel("<b>Red flags:</b> None")  # Label for listing red-flag symptoms
        self.result_redflags_label.setWordWrap(True)  # Wrap long red-flag lists
        card_layout.addWidget(self.result_redflags_label)  # Add red flags label to card

        # User location (clickable link to Google Maps)
        self.result_location_label = QLabel("")  # Label showing resolved location with link to Google Maps
        self.result_location_label.setOpenExternalLinks(True)  # Allow clickable links to open in browser
        self.result_location_label.setWordWrap(True)  # Wrap location text if necessary
        card_layout.addWidget(self.result_location_label)  # Add location label to card

        card_layout.addSpacing(10)  # Spacing between location and facilities section

        # Recommended facilities (scrollable)
        facilities_title = QLabel("<b>Recommended facilities nearby:</b>")  # Title for facilities section
        card_layout.addWidget(facilities_title)  # Add facilities title to card

        fac_scroll = QScrollArea()  # Scroll area to hold facilities list
        fac_scroll.setWidgetResizable(True)  # Allow content to expand to full scroll area width
        fac_scroll.setFixedHeight(180)  # Limit height of scroll area

        fac_inner = QWidget()  # Inner widget inside scroll area
        fac_inner_layout = QVBoxLayout(fac_inner)  # Layout for facilities content
        fac_inner_layout.setContentsMargins(0, 0, 0, 0)  # No internal margins

        self.result_facilities_label = QLabel("")  # Label holding HTML-formatted facilities list
        self.result_facilities_label.setOpenExternalLinks(True)  # Allow clicking links inside list
        self.result_facilities_label.setWordWrap(True)  # Allow wrap for addresses and facility names
        self.result_facilities_label.setTextInteractionFlags(Qt.TextBrowserInteraction)  # Enable link-like behavior
        self.result_facilities_label.setSizePolicy(  # Allow label to expand with scroll area
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )

        fac_inner_layout.addWidget(self.result_facilities_label)  # Add label to inner layout
        fac_inner_layout.addStretch(1)  # Add stretch to push content up inside scroll area

        fac_scroll.setWidget(fac_inner)  # Set inner widget as the scroll area content
        card_layout.addWidget(fac_scroll)  # Add scroll area to card

        card_layout.addStretch(1)  # Push content upwards, leaving flexible space at bottom

        # Save button
        save_btn = QPushButton("Save")  # Button to confirm/save triage entry
        save_btn.setFixedWidth(100)  # Fix button width
        save_btn.setCursor(Qt.PointingHandCursor)  # Use pointing hand cursor
        save_btn.setStyleSheet(  # Style with border and rounded corners
            "QPushButton {"
            "  border-radius: 20px;"
            "  border: 2px solid #000;"
            "  padding: 6px 12px;"
            "  font-size:14px;"
            "  background: white;"
            "}"
            "QPushButton:hover { background: #f3f3f3; }"
        )
        save_btn.clicked.connect(self._on_save_clicked)  # Show a notification when clicked
        card_layout.addWidget(save_btn, alignment=Qt.AlignRight)  # Place Save button at bottom-right of card

        layout.addWidget(card, stretch=3)  # Add main card to Result page layout with larger stretch factor

        # ----- Right: severity scale bar (vertical numbers) -----
        scale_layout = QVBoxLayout()  # Vertical layout for severity scale bar
        scale_layout.setAlignment(Qt.AlignHCenter)  # Horizontally center the scale layout

        top_label = QLabel("Severe")  # Label at top of scale
        top_label.setAlignment(Qt.AlignCenter)  # Center-align text
        top_label.setStyleSheet("font-size:14px;")  # Style for scale labels
        scale_layout.addWidget(top_label)  # Add "Severe" label above bar

        # Bar + numbers side by side
        bar_row = QHBoxLayout()  # Horizontal layout containing the colored bar and the numbers
        bar_row.setAlignment(Qt.AlignCenter)  # Center align the bar row

        bar = QFrame()  # Vertical severity bar
        bar.setFixedWidth(35)  # Fixed width for bar
        bar.setMinimumHeight(250)  # Minimum height for bar
        bar.setStyleSheet(  # Style bar as a vertical gradient from red to green
            "QFrame {"
            "  border-radius: 10px;"
            "  border: 2px solid #000;"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            "              stop:0 #FF4C3B, stop:1 #7CD657);"
            "}"
        )
        bar_row.addWidget(bar)  # Add colored bar to bar row

        self.scale_labels = {}  # Dictionary to hold numeric labels by severity score
        numbers_col = QVBoxLayout()  # Vertical layout for the numbers 4–1
        numbers_col.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # Align numbers left and vertically centered

        for s in [4, 3, 2, 1]:  # Create labels for severity scores from 4 to 1
            lbl = QLabel(str(s))  # Label showing a score number
            lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # Align left and center vertically
            lbl.setStyleSheet("font-size:12px;")  # Default style for numbers
            numbers_col.addWidget(lbl)  # Add this number to the vertical column
            self.scale_labels[s] = lbl  # Store reference to label for later highlighting

        bar_row.addLayout(numbers_col)  # Add numbers column next to the bar
        scale_layout.addLayout(bar_row)  # Add bar row to the main scale layout

        mild_label = QLabel("Mild")  # Label for bottom of scale
        mild_label.setAlignment(Qt.AlignCenter)  # Center-align text
        mild_label.setStyleSheet("font-size:14px;")  # Style for "Mild" label
        scale_layout.addWidget(mild_label)  # Add "Mild" label at bottom of scale

        layout.addLayout(scale_layout, stretch=1)  # Add severity scale to overall page layout

        return page  # Return the completed Result page widget

    # ------------------------------------------------------------------
    # Page 3 – History ("My Data")
    # ------------------------------------------------------------------
    def _build_history_page(self):
        page = QWidget()  # New widget to act as History page
        layout = QHBoxLayout(page)  # Horizontal layout for History page
        layout.setContentsMargins(40, 40, 40, 40)  # Add margins around the page

        card = QFrame()  # Card displaying the history list
        card.setStyleSheet(  # Styled similarly to Result card
            "QFrame {"
            "  background: white;"
            "  border-radius: 30px;"
            "  border: 4px solid #000;"
            "}"
        )
        card_layout = QVBoxLayout(card)  # Vertical layout inside the history card
        card_layout.setContentsMargins(30, 30, 30, 30)  # Internal padding for the card

        title = QLabel("<span style='font-size:22px;'>Your <span style='color:#00C0FF;'>Data</span></span>")  # Title for the history section
        title.setWordWrap(True)  # Wrap long title if necessary
        card_layout.addWidget(title)  # Add title to history card

        scroll = QScrollArea()  # Scroll area for list of history items
        scroll.setWidgetResizable(True)  # Allow the inner widget to resize
        inner = QWidget()  # Inner widget to hold the list of history items
        self.history_items_layout = QVBoxLayout(inner)  # Vertical layout for each history item
        self.history_items_layout.setAlignment(Qt.AlignTop)  # Align items to the top
        scroll.setWidget(inner)  # Set inner widget on scroll area

        card_layout.addWidget(scroll)  # Add scroll area to card

        layout.addWidget(card, stretch=3)  # Add main history card to page layout

        # Right side: severity scale similar to Result page
        scale_layout = QVBoxLayout()  # Vertical layout for severity scale on History page
        scale_layout.setAlignment(Qt.AlignVCenter)  # Center the scale vertically

        top_label = QLabel("Severe")  # Label at top of scale
        top_label.setAlignment(Qt.AlignCenter)  # Center-align "Severe"
        scale_layout.addWidget(top_label)  # Add "Severe" label

        # Bar + numbers side by side
        bar_row = QHBoxLayout()  # Horizontal layout for bar plus numbers
        bar_row.setAlignment(Qt.AlignCenter)  # Center-align the row

        bar = QFrame()  # Colored severity gradient bar
        bar.setFixedWidth(35)  # Fixed width for bar
        bar.setMinimumHeight(250)  # Minimum height for bar
        bar.setStyleSheet(  # Same gradient styling as Result page bar
            "QFrame {"
            "  border-radius: 10px; border: 2px solid #000;"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            "              stop:0 #FF4C3B, stop:1 #7CD657);"
            "}"
        )
        bar_row.addWidget(bar)  # Add bar to bar row

        numbers_col = QVBoxLayout()  # Column for numbers 4–1
        numbers_col.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # Align left and centered vertically
        for s in [4, 3, 2, 1]:  # For each severity level
            lbl = QLabel(str(s))  # Create label with numeric severity
            lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # Align label
            lbl.setStyleSheet("font-size:12px;")  # Style labels
            numbers_col.addWidget(lbl)  # Add number to column
        bar_row.addLayout(numbers_col)  # Add numbers to bar row

        scale_layout.addLayout(bar_row)  # Add bar row to scale layout

        mild_label = QLabel("Mild")  # Label at bottom of scale
        mild_label.setAlignment(Qt.AlignCenter)  # Center "Mild" label
        scale_layout.addWidget(mild_label)  # Add "Mild" text

        layout.addLayout(scale_layout, stretch=1)  # Add scale layout to History page

        return page  # Return the completed History page widget

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------
    def show_home_page(self):
        """Show the Home page in the stacked widget.""" 
        self.stack.setCurrentIndex(0)  # Index 0 corresponds to the Home page

    def show_result_page(self):
        """Show the Result page in the stacked widget."""  
        self.stack.setCurrentIndex(1)  # Index 1 corresponds to the Result page

    def show_history_page(self):
        """Refresh and display the History page."""

        # Clear old items from the history layout
        while self.history_items_layout.count():  # Loop while layout still has child items
            item = self.history_items_layout.takeAt(0)  # Take the first item
            w = item.widget()  # Get the associated widget
            if w is not None:  # If there is a widget
                w.deleteLater()  # Schedule it for deletion to free resources

        records = load_history()  # Load history records from persistent storage
        self.history_records = records  # Store loaded records for later replay in open_history_record()

        for idx, r in enumerate(records):  # Iterate over each record with its index
            score = urgency_to_score(r.urgency_level)  # Convert urgency level to numeric score
            date_str = r.timestamp.strftime("%m/%d/%y")  # Format timestamp as mm/dd/yy

            row_widget = QFrame()  # A frame representing a single history entry
            row_widget.setStyleSheet(  # Style row as a rounded rectangle
                "QFrame {"
                "  border-radius: 20px;"
                "  border: 2px solid #000;"
                "  padding: 6px 14px;"
                "  background: white;"
                "}"
            )
            row_layout = QHBoxLayout(row_widget)  # Horizontal layout for score, text, and date

            # Colored score dot
            score_label = QLabel(str(score))  # Label showing numeric score
            score_label.setAlignment(Qt.AlignCenter)  # Center align score inside its circle
            score_label.setFixedSize(28, 28)  # Fixed small circle size
            if score >= 3:  # If moderate or high severity
                bg = "#FFB347"  # Use orange background
            else:  # Otherwise
                bg = "#A7FF4F"  # Use green background
            score_label.setStyleSheet(  # Style label as colored circular badge
                "QLabel {"
                "  border-radius: 14px;"
                "  border: 2px solid #000;"
                "  font-weight:bold;"
                f"  background: {bg};"
                "}"
            )
            row_layout.addWidget(score_label)  # Add score badge to row

            # Clickable text button (looks like plain text)
            text_button = QPushButton(r.symptoms_text)  # Button showing the stored symptoms text
            text_button.setCursor(Qt.PointingHandCursor)  # Show pointer cursor
            text_button.setStyleSheet(  # Style button to look like plain text
                "QPushButton {"
                "  font-size:14px;"
                "  text-align:left;"
                "  border:none;"
                "  background: transparent;"
                "}"
                "QPushButton:hover { text-decoration: underline; }"
            )
            text_button.setFlat(True)  # Remove button 3D effect
            text_button.clicked.connect(  # Connect to open the selected record
                lambda _, i=idx: self.open_history_record(i)  # Use lambda to capture current index
            )
            row_layout.addWidget(text_button, stretch=1)  # Add text button and let it stretch

            date_label = QLabel(date_str)  # Label showing date of triage
            date_label.setStyleSheet("font-size:14px; color:#555;")  # Subtle styling for date text
            row_layout.addWidget(date_label, alignment=Qt.AlignRight)  # Add date on the right

            self.history_items_layout.addWidget(row_widget)  # Add this row to the vertical history list

        self.history_items_layout.addStretch(1)  # Add stretch to push items to top of scroll
        self.stack.setCurrentIndex(2)  # Show History page in stacked widget

    # ------------------------------------------------------------------
    # Address resolution + triage flow
    # ------------------------------------------------------------------
    def resolve_address(self):
        """Resolve the address text input into coordinates and formatted address.""" 

        address = self.address_edit.text().strip()  # Read and strip address input from the line edit
        if not address:  # If the user didn't enter an address
            QMessageBox.warning(self, "Error", "Please enter an address or ZIP code.")  # Show warning
            return  # Stop processing

        try:
            lat, lon, formatted = geocode_address(address)  # Use geocode function to get lat, lon, and formatted address
        except GeocodingError as e:  # If our custom geocoding error is raised
            QMessageBox.warning(self, "Location error", str(e))  # Show a warning with the error message
            return  # Stop processing
        except Exception as e:  # Catch any other unexpected exception
            QMessageBox.warning(self, "Location error", f"Unexpected error: {e}")  # Show generic error
            return  # Stop processing

        self.lat = lat  # Store latitude in instance variable
        self.lon = lon  # Store longitude in instance variable
        self.formatted_address = formatted  # Store formatted address text
        self.loc_label.setText(f"{formatted} ({lat:.5f}, {lon:.5f})")  # Update location label with text and coordinates

    def run_triage(self):
        """Main triage workflow triggered by the arrow button on the Home page.""" 

        text = self.symptoms_edit.text().strip()  # Get and strip symptoms input
        if not text:  # If no symptom description is provided
            QMessageBox.warning(self, "Error", "Please describe your symptoms.")  # Show error message
            return  # Abort triage

        if self.lat is None or self.lon is None:  # Ensure location is resolved first
            QMessageBox.warning(self, "Error", "Please resolve your location first.")  # Prompt user to set address
            return  # Abort triage

        temp = self._parse_float(self.temp_edit.text(), "Temperature °C", 30, 45)  # Validate and parse temperature
        if temp is False:  # If parsing failed
            return  # Abort triage

        pain = self._parse_int(self.pain_edit.text(), "Pain 0-10", 0, 10)  # Validate and parse pain score
        if pain is False:  # If parsing failed
            return  # Abort triage

        vitals = Vitals(  # Create Vitals dataclass instance from inputs
            temperature_c=temp,  # Temperature in Celsius (or None)
            pain_score=pain,  # Pain score (or None)
            pregnant=self.pregnant_cb.isChecked(),  # Boolean: pregnant?
            trauma=self.trauma_cb.isChecked(),  # Boolean: recent trauma?
        )
        symptoms = SymptomInput(text=text, vitals=vitals)  # Bundle text and vitals into SymptomInput dataclass

        try:
            gemini_raw = call_gemini_for_triage(symptoms)  # Call Gemini API (or model) with symptom input
            decision = apply_rule_safety_layer(symptoms, gemini_raw)  # Apply safety rules on top of raw model output
            recs = recommend_facilities(decision, self.lat, self.lon)  # Get recommended facilities near lat/lon

            append_record(  # Append this triage session to persistent history storage
                symptoms_text=text,
                decision=decision,
                facility_names=[r.facility.name for r in recs],  # Store facility names only
            )

            self.last_symptoms_text = text  # Save last symptoms text for Result page
            self.current_decision = decision  # Save last triage decision
            self.current_recs = recs  # Save facility recommendations

            self._update_result_page()  # Refresh the Result page with latest info
            self.show_result_page()  # Navigate to the Result page

        except Exception as e:  # Catch any errors during triage process
            QMessageBox.critical(self, "Error", f"Triage failed:\n{e}")  # Show critical error dialog

    # ------------------------------------------------------------------
    # Update Result page with latest decision and facilities
    # ------------------------------------------------------------------
    def _update_result_page(self):
        """Populate the Result page UI with current_decision and current_recs.""" 

        if not self.current_decision:  # If there is no decision to show
            return  # Do nothing

        d = self.current_decision  # Short alias for decision
        recs = self.current_recs  # Short alias for facility recommendations

        summary = self.last_symptoms_text.strip()  # Get and strip last symptom text
        if len(summary) > 80:  # Shorten summary if it's too long
            summary = summary[:77] + "..."  # Truncate and add ellipsis
        self.result_symptom_label.setText(summary)  # Set summary text on Result page

        self.result_score_label.setText(str(d.score))  # Display decision's numeric severity score
        self.result_explanation_label.setText(d.explanation or "")  # Show explanation or empty string

        # Recommended action based on urgency
        instruction = self._urgency_to_instruction(d.urgency_level)  # Convert urgency level into text instruction
        self.result_destination_label.setText(  # Set recommended action label
            f"<b>Recommended action:</b> {instruction}"
        )

        if d.red_flags:  # If there are any red flags
            self.result_redflags_label.setText(  # Join red flags into a readable comma-separated string
                "<b>Red flags:</b> " + ", ".join(d.red_flags)
            )
        else:  # No red flags present
            self.result_redflags_label.setText("<b>Red flags:</b> None")  # Show "None"

        # Highlight selected score in the vertical severity scale
        for s, lbl in self.scale_labels.items():  # Iterate over all scale labels
            if s == d.score:  # If this score matches decision's score
                lbl.setStyleSheet("font-size:12px; font-weight:bold;")  # Highlight this number
            else:  # Non-selected scores
                lbl.setStyleSheet("font-size:12px; color:#444;")  # Dim them with gray color

        # Show user’s resolved location and link to Google Maps if available
        if self.lat is not None and self.lon is not None and self.formatted_address:  # Ensure location data exists
            loc_url = f"https://www.google.com/maps/search/?api=1&query={self.lat},{self.lon}"  # Build Google Maps URL
            self.result_location_label.setText(  # Set label with clickable link
                f"<b>Your location:</b> "
                f"<a href='{loc_url}'>{self.formatted_address}</a>"
            )
        else:  # No valid location
            self.result_location_label.setText("")  # Clear location label

        # Render facilities list
        if recs:  # If we have recommended facilities
            items_html = []  # List of HTML list items
            for r in recs:  # For each recommendation
                url = r.maps_url  # URL to Google Maps place
                name = r.facility.name  # Facility name
                addr = r.facility.address or "No address"  # Facility address, with fallback
                dist = f"{r.distance_km:.1f} km away"  # Distance in km formatted as one decimal

                items_html.append(  # Build HTML list item with name, address, and distance
                    "<li>"
                    f"<b><a href='{url}'>{name}</a></b><br>"
                    f"<a href='{url}'>{addr}</a><br>"
                    f"{dist}"
                    "</li>"
                )
            facilities_html = "<ul>" + "\n".join(items_html) + "</ul>"  # Wrap all list items in a <ul>
        else:  # No facilities found
            facilities_html = "<p>No facilities found for this urgency level or radius.</p>"  # Fallback message

        self.result_facilities_label.setText(facilities_html)  # Update the label to display facilities HTML

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _urgency_to_instruction(self, urgency: str) -> str:
        """Map the urgency level string into a user-friendly recommendation sentence.""" 

        u = (urgency or "").upper()  # Normalize urgency string to uppercase, handle None
        if u == "ER":  # Emergency level
            return "Go to an emergency room immediately."  # Strong recommendation
        if u == "URGENT":  # Urgent care level
            return "Go to an urgent care center as soon as possible."  # Moderately strong recommendation
        if u == "CLINIC":  # Clinic level
            return "Go to a clinic / primary care provider for evaluation."  # Clinic recommendation
        return "Stay at home and use self-care, unless symptoms worsen."  # Default home-care advice

    def open_history_record(self, index: int):
        """
        When clicking an item in My Data, reopen that session on the Result page.
        """  

        if index < 0 or index >= len(self.history_records):  # Validate index bounds
            return  # Exit silently if index is invalid

        r = self.history_records[index]  # Get the selected history record

        # Restore symptom text in the home page input (optional but nice)
        self.last_symptoms_text = r.symptoms_text  # Save this symptom text as the current "last"
        self.symptoms_edit.setText(r.symptoms_text)  # Populate Home page input with this past text

        # Reconstruct a minimal TriageDecision from stored urgency
        score = urgency_to_score(r.urgency_level)  # Compute score from urgency
        self.current_decision = TriageDecision(  # Create a minimal decision object
            urgency_level=r.urgency_level,  # Use stored urgency
            score=score,  # Use computed score
            explanation="(Explanation not stored; this is a replay of a past session.)",  # Placeholder explanation
            red_flags=[],  # We do not store red flags in history, so leave empty
        )

        # For now we don't reconstruct facilities from history; just show no facilities
        self.current_recs = []  # Clear facility recommendations for replayed sessions

        # Update the Result page with this synthetic decision
        self._update_result_page()  # Refresh UI on Result page
        self.show_result_page()  # Navigate to Result page

    def _on_save_clicked(self):
        """Show a simple confirmation dialog when user clicks Save on the Result page."""  
        QMessageBox.information(self, "Saved", "This triage entry is saved under My Data.")  # Inform user

    def _parse_float(self, text, label, min_val, max_val):
        """
        Parse a float from a text field and validate its range.
        Returns:
            - parsed float if valid,
            - None if text is empty,
            - False if parsing or validation fails.
        """  

        if not text:  # If the field is empty
            return None  # Treat it as optional and return None
        try:
            v = float(text)  # Try to parse the text as float
        except ValueError:  # If conversion fails
            QMessageBox.warning(self, "Error", f"{label} must be a number.")  # Show error dialog
            return False  # Signal failure
        if not (min_val <= v <= max_val):  # Validate that value lies in the allowed range
            QMessageBox.warning(self, "Error", f"{label} must be between {min_val} and {max_val}.")  # Show error
            return False  # Signal failure
        return v  # Return parsed float if all checks pass

    def _parse_int(self, text, label, min_val, max_val):
        """
        Parse an int from a text field and validate its range.
        Returns:
            - parsed int if valid,
            - None if text is empty,
            - False if parsing or validation fails.
        """  

        if not text:  # If field is empty
            return None  # Treat as unspecified and return None
        try:
            v = int(text)  # Try to parse text as integer
        except ValueError:  # If parsing fails
            QMessageBox.warning(self, "Error", f"{label} must be an integer.")  # Show error dialog
            return False  # Signal failure
        if not (min_val <= v <= max_val):  # Check numeric range constraint
            QMessageBox.warning(self, "Error", f"{label} must be between {min_val} and {max_val}.")  # Show error
            return False  # Signal failure
        return v  # Return valid integer

# ------------------------------------------------------------
# Application entry point
# ------------------------------------------------------------
if __name__ == "__main__":  # Only run the following when this file is executed directly
    app = QApplication(sys.argv)  # Create Qt application, passing command-line arguments
    window = MainWindow()  # Instantiate the main window
    window.resize(1000, 700)  # Set the initial window size
    window.show()  # Show the main window
    sys.exit(app.exec())  # Start Qt event loop and exit with its return code
