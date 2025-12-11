# To run the project
1. Create a .env file under the root folder (or edit it if one already exists) and put in the API keys:

    GEMINI_API_KEY= "PUT KEY HERE"

    GOOGLE_MAPS_API_KEY= "PUT KEY HERE"

2. Run makefile with "make" (Assuming necessary makefile support is installed)
3. Run "python main" (Alternatively with other Python version and/or keyword, such as "python3 -m main", depending on the system setup)

*Be advised that certain system theme would make the UI less readable. Switch to a different theme if necessary*

# To run the unit test
1. Install (if missing) coverage with "pip install coverage" (Or via other package manager of choice)
2. Add coverage to system parameters (This is usually NOT necessary unless the prompt suggests otherwise) 
3. Run "coverage run unit_test.py"
4. Wait for the test to conclude and run "cover report" for statistics
