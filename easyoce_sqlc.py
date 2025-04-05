from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import os
from passporteye import read_mrz
import cv2
import matplotlib.image as mpimg
import string as st
from dateutil import parser
import re
from datetime import datetime, date
import warnings
import mysql.connector
import uvicorn
from PassportDataExtractorobj import PassportDataExtractor
# Suppress warnings
warnings.filterwarnings('ignore')

# Initialize FastAPI app
app = FastAPI()

# Connect to MySQL
def connect_to_db():
    return mysql.connector.connect(
        host="localhost",  # Your MySQL host
        user="root",       # Your MySQL user
        password="123123", # Your MySQL password
        database="passport_db"  # Your MySQL database name
    )

# Initialize the extractor
extractor = PassportDataExtractor()

# FastAPI endpoint
@app.post("/extract-passport-details/")
async def extract_passport_details(file: UploadFile = File(...)):
    try:
        # Save the uploaded image to a temporary file using os.path
        temp_dir = os.path.join(os.getcwd(), "temp_uploads")
        os.makedirs(temp_dir, exist_ok=True)
        tmpfile_path = os.path.join(temp_dir, file.filename)

        with open(tmpfile_path, "wb") as buffer:
            buffer.write(await file.read())

        # Extract data from the image
        user_info = extractor.get_data(tmpfile_path)

        # Clean up the temporary file
        if os.path.exists(tmpfile_path):
            os.remove(tmpfile_path)

        # Connect to MySQL
        db = connect_to_db()
        cursor = db.cursor()

        # Insert data into MySQL
        query = """
        INSERT INTO passport_d (
            name, date_of_birth, date_of_issue, date_of_expiry, nationality, passport_type, passport_number,sex
        ) VALUES (%s, %s, %s, %s, %s, %s, %s,%s)
        """
        values = (
        user_info['name'],
        datetime.strptime(user_info['date_of_birth'], '%m/%Y').date() if user_info['date_of_birth'] and user_info['date_of_birth'] != 'Not Found' else None,
        datetime.strptime(user_info['date_of_issue'], '%m/%Y').date() if user_info['date_of_issue'] and user_info['date_of_issue'] != 'Not Found' else None,
        datetime.strptime(user_info['date_of_expiry'], '%m/%Y').date() if user_info['date_of_expiry'] and user_info['date_of_expiry'] != 'Not Found' else None,
        user_info['nationality'],
        user_info['passport_type'],
        user_info['passport_number'],
        user_info["sex"],
    )


        cursor.execute(query, values)
        db.commit()

        # Close the database connection
        cursor.close()
        db.close()

        # Return the extracted data
        return JSONResponse(content={"message": "Passport details extracted and stored successfully", "data": user_info})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
    

@app.get("/get-passport-details/")
async def get_passport_details():
    try:
        # Connect to MySQL
        db = connect_to_db()
        cursor = db.cursor(dictionary=True)

        # Retrieve all records
        cursor.execute("SELECT * FROM passport_d")
        records = cursor.fetchall()

        # Convert date fields to string
        for record in records:
            for key, value in record.items():
                if isinstance(value, (date, datetime)):  # Convert date/datetime objects
                    record[key] = value.isoformat()

        # Close the database connection
        cursor.close()
        db.close()

        return JSONResponse(content={"message": "Passport details retrieved successfully", "data": records})

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Run the FastAPI server
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)