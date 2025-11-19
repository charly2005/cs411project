# main.py
import sys

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QCheckBox,
    QPushButton,
    QMessageBox,
    QStackedWidget,
    QScrollArea,
    QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Qt

from models import Vitals, SymptomInput
from triage_engine import call_gemini_for_triage, apply_rule_safety_layer
from facilities_google import recommend_facilities
from history import append_record, load_history
from geolocation import geocode_address, GeocodingError


def urgency_to_score(urgency: str) -> int:
    """Map urgency level to numeric score 1–4."""
    u = (urgency or "").upper()
    if u == "ER":
        return 4
    if u == "URGENT":
        return 3
    if u == "CLINIC":
        return 2
    return 1  # HOME / default


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("CareRoute Desktop")

        # Last resolved user location
        self.lat = None
        self.lon = None
        self.formatted_address = None

        # Last triage result
        self.last_symptoms_text = ""
        self.current_decision = None
        self.current_recs = []

        self._build_shell()
        self._build_pages()

    # ------------------------------------------------------------------
    # Shell layout: header, stacked pages, footer disclaimer
    # ------------------------------------------------------------------
    def _build_shell(self):
        main_layout = QVBoxLayout(self)

        # ---------- Header (CareRoute + My Data + Home) ----------
        header_layout = QHBoxLayout()

        # "My Data" folder button (top-left)
        self.my_data_button = QPushButton("📁  My Data")
        self.my_data_button.setCursor(Qt.PointingHandCursor)
        self.my_data_button.setStyleSheet(
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
        self.my_data_button.clicked.connect(self.show_history_page)
        header_layout.addWidget(self.my_data_button, alignment=Qt.AlignLeft)

        # Title in the center
        title_layout = QVBoxLayout()
        self.title_label = QLabel(
            "<span style='font-size:32px; font-weight:bold;'>"
            "<span style='color:#7FFFD4;'>Care</span>"
            "<span style='color:#00C0FF;'>Route</span>"
            "</span>"
        )
        self.title_label.setAlignment(Qt.AlignCenter)

        subtitle = QLabel("AI-Powered Triage Engine")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size:18px; font-weight:bold;")

        title_layout.addWidget(self.title_label)
        title_layout.addWidget(subtitle)

        header_layout.addLayout(title_layout, stretch=1)

        # Simple "Home" button on top-right for navigation
        self.home_button = QPushButton("Home")
        self.home_button.setCursor(Qt.PointingHandCursor)
        self.home_button.setStyleSheet(
            "QPushButton { border: none; font-size: 14px; color: #007ACC; }"
            "QPushButton:hover { text-decoration: underline; }"
        )
        self.home_button.clicked.connect(self.show_home_page)
        header_layout.addWidget(self.home_button, alignment=Qt.AlignRight)

        main_layout.addLayout(header_layout)

        # ---------- Stacked pages ----------
        self.stack = QStackedWidget()
        main_layout.addWidget(self.stack, stretch=1)

        # ---------- Disclaimer (bottom) ----------
        disclaimer = QLabel(
            "The content on this application does not substitute medical advice. "
            "Always consult a licensed professional for personalized medical guidance."
        )
        disclaimer.setAlignment(Qt.AlignCenter)
        disclaimer.setWordWrap(True)
        disclaimer.setStyleSheet("font-size:10px; color:#555; margin-top:8px;")
        main_layout.addWidget(disclaimer)

    # ------------------------------------------------------------------
    # Build individual pages and add them to stacked widget
    # ------------------------------------------------------------------
    def _build_pages(self):
        self.home_page = self._build_home_page()
        self.result_page = self._build_result_page()
        self.history_page = self._build_history_page()

        self.stack.addWidget(self.home_page)    # index 0
        self.stack.addWidget(self.result_page)  # index 1
        self.stack.addWidget(self.history_page) # index 2

        self.show_home_page()

    # ------------------------------------------------------------------
    # Page 1 – Home (美化版)
    # ------------------------------------------------------------------
    def _build_home_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setAlignment(Qt.AlignTop)

        layout.addSpacing(40)

        # 顶部问题标题
        question = QLabel("What’s bothering you today?")
        question.setAlignment(Qt.AlignCenter)
        question.setStyleSheet("font-size:28px; font-weight:bold;")
        layout.addWidget(question)

        layout.addSpacing(40)

        # --- 中间大输入行: [ 大输入框 ] [ mic ] [ 绿色箭头 ] ---
        center_row = QHBoxLayout()
        center_row.setAlignment(Qt.AlignCenter)

        self.symptoms_edit = QLineEdit()
        self.symptoms_edit.setPlaceholderText("Enter question here . . .")
        self.symptoms_edit.setMinimumWidth(600)
        self.symptoms_edit.setMinimumHeight(54)
        self.symptoms_edit.setStyleSheet(
            "QLineEdit {"
            "  font-size:16px;"
            "  padding: 10px 16px;"
            "  border-radius: 27px;"
            "  border: 2px solid #444;"
            "  background: white;"
            "}"
        )
        center_row.addWidget(self.symptoms_edit)

        # Mic 图标（目前只是装饰）
        mic_btn = QPushButton("🎤")
        mic_btn.setEnabled(False)
        mic_btn.setFixedSize(54, 54)
        mic_btn.setStyleSheet(
            "QPushButton {"
            "  border-radius: 27px;"
            "  border: 2px solid #ccc;"
            "  background: #f2f2f2;"
            "  font-size:20px;"
            "}"
        )
        center_row.addSpacing(8)
        center_row.addWidget(mic_btn)

        # 绿色箭头按钮
        self.triage_button = QPushButton("➜")
        self.triage_button.setCursor(Qt.PointingHandCursor)
        self.triage_button.setFixedSize(60, 60)
        self.triage_button.setStyleSheet(
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
        self.triage_button.clicked.connect(self.run_triage)
        center_row.addSpacing(12)
        center_row.addWidget(self.triage_button)

        layout.addLayout(center_row)

        layout.addSpacing(30)

        # === 下方一块整体 panel：地址 + 体征，整体居中 ===
        bottom_panel = QFrame()
        bottom_panel.setStyleSheet("QFrame { background: transparent; }")
        panel_layout = QVBoxLayout(bottom_panel)
        panel_layout.setAlignment(Qt.AlignTop)
        panel_layout.setContentsMargins(0, 0, 0, 0)

        # --- Location 行 ---
        loc_layout = QHBoxLayout()
        loc_layout.setSpacing(10)

        self.address_edit = QLineEdit()
        self.address_edit.setPlaceholderText(
            "Enter your address or ZIP code (required for nearby facilities)"
        )
        self.address_edit.setMinimumWidth(450)
        self.address_edit.setStyleSheet(
            "QLineEdit {"
            "  font-size:13px;"
            "  padding: 6px 10px;"
            "  border-radius: 18px;"
            "  border: 1px solid #bbb;"
            "  background: white;"
            "}"
        )
        loc_layout.addWidget(self.address_edit, stretch=3)

        self.loc_button = QPushButton("Resolve Address")
        self.loc_button.setCursor(Qt.PointingHandCursor)
        self.loc_button.setStyleSheet(
            "QPushButton {"
            "  padding: 6px 12px;"
            "  border-radius: 16px;"
            "  border: 1px solid #888;"
            "  background: #f7f7f7;"
            "  font-size:12px;"
            "}"
            "QPushButton:hover { background:#eee; }"
        )
        self.loc_button.clicked.connect(self.resolve_address)
        loc_layout.addWidget(self.loc_button)

        panel_layout.addLayout(loc_layout)

        # 解析后的地址显示为一行小字
        self.loc_label = QLabel("Location: not set")
        self.loc_label.setWordWrap(True)
        self.loc_label.setStyleSheet("font-size:11px; color:#555; margin-top:4px;")
        panel_layout.addWidget(self.loc_label)

        panel_layout.addSpacing(10)

        # --- Vitals 行 ---
        vitals_layout = QHBoxLayout()
        vitals_layout.setSpacing(12)

        self.temp_edit = QLineEdit()
        self.temp_edit.setPlaceholderText("Temperature °C (optional)")
        self.temp_edit.setFixedWidth(200)
        self.temp_edit.setStyleSheet(
            "QLineEdit {"
            "  font-size:12px;"
            "  padding: 4px 8px;"
            "  border-radius: 14px;"
            "  border: 1px solid #bbb;"
            "  background: white;"
            "}"
        )
        vitals_layout.addWidget(self.temp_edit)

        self.pain_edit = QLineEdit()
        self.pain_edit.setPlaceholderText("Pain 0-10 (optional)")
        self.pain_edit.setFixedWidth(200)
        self.pain_edit.setStyleSheet(
            "QLineEdit {"
            "  font-size:12px;"
            "  padding: 4px 8px;"
            "  border-radius: 14px;"
            "  border: 1px solid #bbb;"
            "  background: white;"
            "}"
        )
        vitals_layout.addWidget(self.pain_edit)

        self.pregnant_cb = QCheckBox("Pregnant")
        self.pregnant_cb.setStyleSheet("font-size:12px;")
        vitals_layout.addWidget(self.pregnant_cb)

        self.trauma_cb = QCheckBox("Recent trauma")
        self.trauma_cb.setStyleSheet("font-size:12px;")
        vitals_layout.addWidget(self.trauma_cb)

        vitals_layout.addStretch(1)
        panel_layout.addLayout(vitals_layout)

        # 整块 panel 居中放在页面中间
        layout.addWidget(bottom_panel, alignment=Qt.AlignHCenter)

        layout.addStretch(1)
        return page

    # ------------------------------------------------------------------
    # Page 2 – Result
    # ------------------------------------------------------------------
    def _build_result_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)

        # ----- Left: big card -----
        card = QFrame()
        card.setStyleSheet(
            "QFrame {"
            "  background: white;"
            "  border-radius: 30px;"
            "  border: 4px solid #000;"
            "}"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(30, 30, 30, 30)

        self.result_symptom_label = QLabel("I am feeling a small headache . . .")
        self.result_symptom_label.setStyleSheet("font-size:22px; font-weight:bold;")
        self.result_symptom_label.setWordWrap(True)
        card_layout.addWidget(self.result_symptom_label)

        card_layout.addSpacing(10)

        # Score + explanation
        score_row = QHBoxLayout()

        self.result_score_label = QLabel("1")
        self.result_score_label.setStyleSheet(
            "font-size:72px; font-weight:bold; color:#88D840;"
        )
        score_row.addWidget(self.result_score_label, alignment=Qt.AlignTop)

        self.result_explanation_label = QLabel("")
        self.result_explanation_label.setWordWrap(True)
        self.result_explanation_label.setStyleSheet("font-size:14px;")
        score_row.addWidget(self.result_explanation_label)

        card_layout.addLayout(score_row)

        card_layout.addSpacing(10)

        # Red flags line
        self.result_redflags_label = QLabel("<b>Red flags:</b> None")
        self.result_redflags_label.setWordWrap(True)
        card_layout.addWidget(self.result_redflags_label)

        # User location (clickable link to Google Maps)
        self.result_location_label = QLabel("")
        self.result_location_label.setOpenExternalLinks(True)
        self.result_location_label.setWordWrap(True)
        card_layout.addWidget(self.result_location_label)

        card_layout.addSpacing(10)

        # Recommended facilities (scrollable)
        facilities_title = QLabel("<b>Recommended facilities nearby:</b>")
        card_layout.addWidget(facilities_title)

        fac_scroll = QScrollArea()
        fac_scroll.setWidgetResizable(True)
        fac_scroll.setFixedHeight(180)

        fac_inner = QWidget()
        fac_inner_layout = QVBoxLayout(fac_inner)
        fac_inner_layout.setContentsMargins(0, 0, 0, 0)

        self.result_facilities_label = QLabel("")
        self.result_facilities_label.setOpenExternalLinks(True)
        self.result_facilities_label.setWordWrap(True)
        self.result_facilities_label.setTextInteractionFlags(Qt.TextBrowserInteraction)
        self.result_facilities_label.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )

        fac_inner_layout.addWidget(self.result_facilities_label)
        fac_inner_layout.addStretch(1)

        fac_scroll.setWidget(fac_inner)
        card_layout.addWidget(fac_scroll)

        card_layout.addStretch(1)

        # Save button
        save_btn = QPushButton("Save")
        save_btn.setFixedWidth(100)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.setStyleSheet(
            "QPushButton {"
            "  border-radius: 20px;"
            "  border: 2px solid #000;"
            "  padding: 6px 12px;"
            "  font-size:14px;"
            "  background: white;"
            "}"
            "QPushButton:hover { background: #f3f3f3; }"
        )
        save_btn.clicked.connect(self._on_save_clicked)
        card_layout.addWidget(save_btn, alignment=Qt.AlignRight)

        layout.addWidget(card, stretch=3)

        # ----- Right: severity scale bar (vertical numbers) -----
        scale_layout = QVBoxLayout()
        scale_layout.setAlignment(Qt.AlignHCenter)

        top_label = QLabel("Severe")
        top_label.setAlignment(Qt.AlignCenter)
        top_label.setStyleSheet("font-size:14px;")
        scale_layout.addWidget(top_label)

        # Bar + numbers side by side
        bar_row = QHBoxLayout()
        bar_row.setAlignment(Qt.AlignCenter)

        bar = QFrame()
        bar.setFixedWidth(35)
        bar.setMinimumHeight(250)
        bar.setStyleSheet(
            "QFrame {"
            "  border-radius: 10px;"
            "  border: 2px solid #000;"
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            "              stop:0 #FF4C3B, stop:1 #7CD657);"
            "}"
        )
        bar_row.addWidget(bar)

        self.scale_labels = {}
        numbers_col = QVBoxLayout()
        numbers_col.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        for s in [4, 3, 2, 1]:
            lbl = QLabel(str(s))
            lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            lbl.setStyleSheet("font-size:12px;")
            numbers_col.addWidget(lbl)
            self.scale_labels[s] = lbl

        bar_row.addLayout(numbers_col)
        scale_layout.addLayout(bar_row)

        mild_label = QLabel("Mild")
        mild_label.setAlignment(Qt.AlignCenter)
        mild_label.setStyleSheet("font-size:14px;")
        scale_layout.addWidget(mild_label)

        layout.addLayout(scale_layout, stretch=1)


        return page

    # ------------------------------------------------------------------
    # Page 3 – History ("My Data")
    # ------------------------------------------------------------------
    def _build_history_page(self):
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)

        card = QFrame()
        card.setStyleSheet(
            "QFrame {"
            "  background: white;"
            "  border-radius: 30px;"
            "  border: 4px solid #000;"
            "}"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(30, 30, 30, 30)

        title = QLabel("<span style='font-size:22px;'>Your <span style='color:#00C0FF;'>Data</span></span>")
        title.setWordWrap(True)
        card_layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        self.history_items_layout = QVBoxLayout(inner)
        self.history_items_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(inner)

        card_layout.addWidget(scroll)

        layout.addWidget(card, stretch=3)

        scale_layout = QVBoxLayout()
        scale_layout.setAlignment(Qt.AlignVCenter)

        top_label = QLabel("Severe")
        top_label.setAlignment(Qt.AlignCenter)
        scale_layout.addWidget(top_label)

        bar = QFrame()
        bar.setFixedWidth(35)
        bar.setMinimumHeight(250)
        bar.setStyleSheet(
            "QFrame {"
            '  border-radius: 10px; border: 2px solid #000;'
            "  background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            "              stop:0 #FF4C3B, stop:1 #7CD657);"
            "}"
        )
        scale_layout.addWidget(bar, alignment=Qt.AlignCenter)

        label_row = QHBoxLayout()
        for s in [4, 3, 2, 1]:
            lbl = QLabel(str(s))
            lbl.setAlignment(Qt.AlignLeft)
            lbl.setStyleSheet("font-size:12px;")
            label_row.addWidget(lbl)
        scale_layout.addLayout(label_row)

        mild_label = QLabel("Mild")
        mild_label.setAlignment(Qt.AlignCenter)
        scale_layout.addWidget(mild_label)

        layout.addLayout(scale_layout, stretch=1)

        return page

    # ------------------------------------------------------------------
    # Navigation helpers
    # ------------------------------------------------------------------
    def show_home_page(self):
        self.stack.setCurrentIndex(0)

    def show_result_page(self):
        self.stack.setCurrentIndex(1)

    def show_history_page(self):
        while self.history_items_layout.count():
            item = self.history_items_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        records = load_history()

        for r in records:
            score = urgency_to_score(r.urgency_level)
            date_str = r.timestamp.strftime("%m/%d/%y")

            row_widget = QFrame()
            row_widget.setStyleSheet(
                "QFrame {"
                "  border-radius: 20px;"
                "  border: 2px solid #000;"
                "  padding: 6px 14px;"
                "  background: white;"
                "}"
            )
            row_layout = QHBoxLayout(row_widget)

            score_label = QLabel(str(score))
            score_label.setAlignment(Qt.AlignCenter)
            score_label.setFixedSize(28, 28)
            if score >= 3:
                bg = "#FFB347"
            else:
                bg = "#A7FF4F"
            score_label.setStyleSheet(
                "QLabel {"
                "  border-radius: 14px;"
                "  border: 2px solid #000;"
                "  font-weight:bold;"
                f"  background: {bg};"
                "}"
            )
            row_layout.addWidget(score_label)

            text_label = QLabel(r.symptoms_text)
            text_label.setStyleSheet("font-size:14px;")
            text_label.setWordWrap(True)
            row_layout.addWidget(text_label, stretch=1)

            date_label = QLabel(date_str)
            date_label.setStyleSheet("font-size:14px; color:#555;")
            row_layout.addWidget(date_label, alignment=Qt.AlignRight)

            self.history_items_layout.addWidget(row_widget)

        self.history_items_layout.addStretch(1)

        self.stack.setCurrentIndex(2)

    # ------------------------------------------------------------------
    # Address resolution + triage flow
    # ------------------------------------------------------------------
    def resolve_address(self):
        address = self.address_edit.text().strip()
        if not address:
            QMessageBox.warning(self, "Error", "Please enter an address or ZIP code.")
            return

        try:
            lat, lon, formatted = geocode_address(address)
        except GeocodingError as e:
            QMessageBox.warning(self, "Location error", str(e))
            return
        except Exception as e:
            QMessageBox.warning(self, "Location error", f"Unexpected error: {e}")
            return

        self.lat = lat
        self.lon = lon
        self.formatted_address = formatted
        self.loc_label.setText(f"{formatted} ({lat:.5f}, {lon:.5f})")

    def run_triage(self):
        text = self.symptoms_edit.text().strip()
        if not text:
            QMessageBox.warning(self, "Error", "Please describe your symptoms.")
            return

        if self.lat is None or self.lon is None:
            QMessageBox.warning(self, "Error", "Please resolve your location first.")
            return

        temp = self._parse_float(self.temp_edit.text(), "Temperature °C", 30, 45)
        if temp is False:
            return

        pain = self._parse_int(self.pain_edit.text(), "Pain 0-10", 0, 10)
        if pain is False:
            return

        vitals = Vitals(
            temperature_c=temp,
            pain_score=pain,
            pregnant=self.pregnant_cb.isChecked(),
            trauma=self.trauma_cb.isChecked(),
        )
        symptoms = SymptomInput(text=text, vitals=vitals)

        try:
            gemini_raw = call_gemini_for_triage(symptoms)
            decision = apply_rule_safety_layer(symptoms, gemini_raw)
            recs = recommend_facilities(decision, self.lat, self.lon)

            append_record(
                symptoms_text=text,
                decision=decision,
                facility_names=[r.facility.name for r in recs],
            )

            self.last_symptoms_text = text
            self.current_decision = decision
            self.current_recs = recs

            self._update_result_page()
            self.show_result_page()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Triage failed:\n{e}")

    # ------------------------------------------------------------------
    # Update Result page with latest decision and facilities
    # ------------------------------------------------------------------
    def _update_result_page(self):
        if not self.current_decision:
            return

        d = self.current_decision
        recs = self.current_recs

        summary = self.last_symptoms_text.strip()
        if len(summary) > 80:
            summary = summary[:77] + "..."
        self.result_symptom_label.setText(summary)

        self.result_score_label.setText(str(d.score))
        self.result_explanation_label.setText(d.explanation or "")

        if d.red_flags:
            self.result_redflags_label.setText(
                "<b>Red flags:</b> " + ", ".join(d.red_flags)
            )
        else:
            self.result_redflags_label.setText("<b>Red flags:</b> None")

        for s, lbl in self.scale_labels.items():
            if s == d.score:
                lbl.setStyleSheet("font-size:12px; font-weight:bold;")
            else:
                lbl.setStyleSheet("font-size:12px; color:#444;")

        if self.lat is not None and self.lon is not None and self.formatted_address:
            loc_url = f"https://www.google.com/maps/search/?api=1&query={self.lat},{self.lon}"
            self.result_location_label.setText(
                f"<b>Your location:</b> "
                f"<a href='{loc_url}'>{self.formatted_address}</a>"
            )
        else:
            self.result_location_label.setText("")

        if recs:
            items_html = []
            for r in recs:
                url = r.maps_url
                name = r.facility.name
                addr = r.facility.address or "No address"
                dist = f"{r.distance_km:.1f} km away"

                items_html.append(
                    "<li>"
                    f"<b><a href='{url}'>{name}</a></b><br>"
                    f"<a href='{url}'>{addr}</a><br>"
                    f"{dist}"
                    "</li>"
                )
            facilities_html = "<ul>" + "\n".join(items_html) + "</ul>"
        else:
            facilities_html = "<p>No facilities found for this urgency level or radius.</p>"

        self.result_facilities_label.setText(facilities_html)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _on_save_clicked(self):
        QMessageBox.information(self, "Saved", "This triage entry is saved under My Data.")

    def _parse_float(self, text, label, min_val, max_val):
        if not text:
            return None
        try:
            v = float(text)
        except ValueError:
            QMessageBox.warning(self, "Error", f"{label} must be a number.")
            return False
        if not (min_val <= v <= max_val):
            QMessageBox.warning(self, "Error", f"{label} must be between {min_val} and {max_val}.")
            return False
        return v

    def _parse_int(self, text, label, min_val, max_val):
        if not text:
            return None
        try:
            v = int(text)
        except ValueError:
            QMessageBox.warning(self, "Error", f"{label} must be an integer.")
            return False
        if not (min_val <= v <= max_val):
            QMessageBox.warning(self, "Error", f"{label} must be between {min_val} and {max_val}.")
            return False
        return v


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.resize(1000, 700)
    window.show()
    sys.exit(app.exec())
