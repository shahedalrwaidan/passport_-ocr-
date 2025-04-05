import os
import easyocr
from passporteye import read_mrz
import cv2
import matplotlib.image as mpimg
import string as st
from dateutil import parser
import re
import warnings
import mysql.connector
from datetime import datetime
import uvicorn
from pycountry import countries

# Suppress warnings
warnings.filterwarnings('ignore')



# Hardcoded country codes for US and Jordan
COUNTRY_CODES = [
    {"code": "USA", "name": "UNITED STATES OF AMERICA"},
    {"code": "JOR", "name": "JORDAN"}
]
# PassportDataExtractor class
class PassportDataExtractor:
    def __init__(self, gpu=True):
        self.reader = easyocr.Reader(lang_list=['en'], gpu=gpu)
        self.country_codes = COUNTRY_CODES  # Use hardcoded country codes
        self.country_code_pattern = r'\b[A-Z]{3}\b' 

    def parse_date(self, date_string):
        try:
            # Parse the date assuming the year is in the range 1900-2099
            date = parser.parse(date_string, yearfirst=True).date()
            return date.strftime('%d/%m/%Y')
        except ValueError:
            return None

    def clean(self, string):
        return ''.join(char for char in string if char.isalnum()).upper()

    def get_country_name(self, country_code):
        try:
            return countries.get(alpha_3=country_code).name
        except:
            return f"Unknown Country ({country_code})"


    def find_issuing_date(self,ocr_text,num):
        """
        Extracts the month and year from OCR text using predefined patterns.

        Args:
        ocr_text (list): List of strings containing OCR results.

        Returns:
        str: The extracted month and year in 'MM/YYYY' format, or 'Not Found' if no valid date is found.
        """
        # Define patterns to look for month and year in the OCR text
        month_year_patterns = [
            r'\b(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\b \d{4}',  # Matches 'MMM YYYY'
            r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b \d{4}',  # Matches 'Month YYYY'
            r'\d{2}[-/]\d{4}'            ]
        all_matches = []  # To store all found matches

        # Iterate through each line in the OCR text
        for line in ocr_text:
            for pattern in month_year_patterns:
                # Find all matches for the current pattern
                month_year_matches = re.findall(pattern, line, re.IGNORECASE)
                all_matches.extend(month_year_matches)

        # If there are multiple matches, process the second one
        if len(all_matches) > num:
            second_match = all_matches[num]
            try:
                # Parse the second match to extract month and year
                parsed_date = parser.parse(second_match, fuzzy=True)
                return parsed_date.strftime('%m/%Y')  # Format as 'MM/YYYY'
            except ValueError:
                return "Not Found"
        
        # Return "Not Found" if no second match exists
        return "Not Found"


    def find_month_and_year(self, ocr_text):
            """
            Extracts the month and year from OCR text using predefined patterns.

            Args:
                ocr_text (list): List of strings containing OCR results.

            Returns:
                str: The extracted month and year in 'MM/YYYY' format, or 'Not Found' if no valid date is found.
            """
            # Define patterns to look for month and year in the OCR text
            month_year_patterns = [
                r'\b(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\b \d{4}',  # Matches 'MMM YYYY'
                r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b \d{4}',  # Matches 'Month YYYY'
                r'\d{2}[-/]\d{4}',  # Matches 'MM-YYYY' or 'MM/YYYY'
            ]

            # Iterate through each line in the OCR text
            for line in ocr_text:
                for pattern in month_year_patterns:
                    # Find all matches for the current pattern
                    month_year_matches = re.findall(pattern, line, re.IGNORECASE)
                    for match in month_year_matches:
                        try:
                            # Parse the match to extract month and year
                            parsed_date = parser.parse(match, fuzzy=True)
                            return parsed_date.strftime('%m/%Y')  # Format as 'MM/YYYY'
                        except ValueError:
                            continue

            # Return 'Not Found' if no valid month and year are found
            return 'Not Found'
    def find_country_in_text(self, ocr_text):
        """
        Searches for country codes in OCR text and returns the country name.

        Args:
            ocr_text (list): List of strings containing OCR results.

        Returns:
            str: The country name found, or 'Unknown Country' if no valid country code is found.
        """
        # Iterate through the OCR text to search for country codes using the pattern
        for line in ocr_text:
            # Search for any 3-letter uppercase country codes in the text
            country_codes = re.findall(self.country_code_pattern, line)
            
            # Iterate over the found country codes and get the corresponding country names
            for code in country_codes:
                country_name = self.get_country_name(code)
                if country_name != f"Unknown Country ({code})":
                    return country_name  # Return the first valid country name found

        return "Unknown Country"  # If no valid country is found
    def extract_sex(self,ocr_text):
            """
            Extracts the sex (gender) from OCR text using predefined keywords.

            Args:
                ocr_text (list): List of strings containing OCR results.

            Returns:
                str: The extracted sex (gender), or 'Not Found' if no valid gender is found.
            """
                # Define a pattern to look for the term 'Sex' or variations like 'Sexo'
            sex_patterns = [
            r'\b(M|F)\b',  # Matches ' M', 'M', etc.
            ]

            # Iterate through each line in the OCR text
            for line in ocr_text:
                for pattern in sex_patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        # If a match is found, return the sex
                        sex = match.group(1)
                        return sex.upper()  # Return 'M' or 'F'

            return "Not Found"
    def get_data(self, img_name):
        user_info = {}
        # Create a temporary file path using os.path
        tmpfile_path = os.path.join(os.getcwd(), "temp_roi.png")

        try:
            mrz = read_mrz(img_name, save_roi=True)
            if mrz:
                mpimg.imsave(tmpfile_path, mrz.aux['roi'], cmap='gray')
                img = cv2.imread(tmpfile_path)
                img = cv2.resize(img, (1110, 140))
                allowlist = st.ascii_letters + st.digits + '< '
                code = self.reader.readtext(img, paragraph=False, detail=0, allowlist=allowlist)
                if len(code) < 2:
                    return {"error": f'Insufficient OCR results for image {img_name}.'}

                a, b = code[0].upper(), code[1].upper()

                if len(a) < 44:
                    a = a + '<' * (44 - len(a))
                if len(b) < 44:
                    b = b + '<' * (44 - len(b))

                surname_names = a[7:44].split('<<', 1)
                surname, names = surname_names if len(surname_names) == 2 else (surname_names[0], '')
                name = names.replace('<', ' ').strip().upper()
                surname = surname.replace('<', ' ').strip().upper()
                full_img = cv2.imread(img_name)
                ocr_results = self.reader.readtext(full_img, detail=0)
                print("ocr_reasults : ",ocr_results)
                a=self.clean(a)
                b=self.clean(b)

                user_info['name'] = f"{self.clean(name)}{surname}"
                user_info['date_of_birth'] = self.find_month_and_year(ocr_results)
                user_info['date_of_issue'] = self.find_issuing_date(ocr_results,1)
                user_info['sex']=self.extract_sex(ocr_results)
                user_info['date_of_expiry'] = self.find_issuing_date(ocr_results,2)
                user_info['nationality'] = self.find_country_in_text(ocr_results)

                #user_info['nationality'] = self.get_country_name(self.clean(a[1:4]))
                user_info['passport_type'] = self.clean(a[0:1])
                user_info['passport_number'] = self.clean(b[0:9])

            else:
                return {"error": f'Machine cannot read image {img_name}.'}

        finally:
            # Clean up the temporary file
            if os.path.exists(tmpfile_path):
                os.remove(tmpfile_path)

        return user_info