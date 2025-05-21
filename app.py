from flask import Flask, request, jsonify, send_file
import requests
import pydicom
import cv2
import numpy as np
import os
import uuid

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 🔁 Get the first SeriesInstanceUID from the Study
def get_first_series(dicom_url):
    series_url = f"{dicom_url}/series"
    response = requests.get(series_url, headers={"Accept": "application/json"})
    if response.status_code != 200:
        raise Exception(f"Failed to fetch series: {response.status_code}")
    series_list = response.json()
    if not series_list:
        raise Exception("No series found in study")
    return series_list[0]['0020000E']['Value'][0]  # SeriesInstanceUID

# 🔁 Get the first SOPInstanceUID from the Series
def get_first_instance(dicom_url, series_uid):
    instance_url = f"{dicom_url}/series/{series_uid}/instances"
    response = requests.get(instance_url, headers={"Accept": "application/json"})
    if response.status_code != 200:
        raise Exception(f"Failed to fetch instances: {response.status_code}")
    instances = response.json()
    if not instances:
        raise Exception("No instances found in series")
    return instances[0]['00080018']['Value'][0]  # SOPInstanceUID

# 📥 Download a DICOM instance
def download_dicom_file(study_uid, series_uid, instance_uid, base_url, save_path):
    file_url = f"{base_url}/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}"
    headers = {"Accept": "application/dicom; transfer-syntax=*"}
    response = requests.get(file_url, headers=headers)
    if response.status_code == 200:
        with open(save_path, "wb") as f:
            f.write(response.content)
        return save_path
    else:
        raise Exception(f"Failed to download DICOM file: {response.status_code}")

# 🖼️ Convert DICOM to PNG
def dicom_to_png(dicom_path, png_path):
    ds = pydicom.dcmread(dicom_path)
    arr = ds.pixel_array
    img = cv2.convertScaleAbs(arr, alpha=255.0 / arr.max())
    cv2.imwrite(png_path, img)
    return png_path

# 🚀 Main endpoint
@app.route("/process-dicom", methods=["POST"])
def process_dicom():
    data = request.get_json()
    dicom_url = data.get("dicom_url")
    if not dicom_url:
        return jsonify({"error": "Missing dicom_url"}), 400

    try:
        # Extract Study UID from URL
        study_uid = dicom_url.split("/")[-1]
        base_url = "/".join(dicom_url.split("/")[:6])  # http://host:port/dcm4chee-arc/aets/DCM4CHEE/rs

        # Get Series & Instance UIDs
        series_uid = get_first_series(dicom_url)
        instance_uid = get_first_instance(dicom_url, series_uid)

        # Download actual DICOM file
        unique_name = str(uuid.uuid4())
        dicom_path = os.path.join(UPLOAD_FOLDER, unique_name + ".dcm")
        png_path = os.path.join(UPLOAD_FOLDER, unique_name + ".png")

        download_dicom_file(study_uid, series_uid, instance_uid, base_url, dicom_path)
        dicom_to_png(dicom_path, png_path)

        return jsonify({
            "message": "DICOM processed successfully",
            "image_url": f"/image/{unique_name}.png",
            "prompt": "This is a medical image extracted from a DICOM file. Please analyze and provide a radiologist-style interpretation."
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 🖼️ Serve image
@app.route("/image/<filename>")
def get_image(filename):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "Image not found"}), 404
    return send_file(file_path, mimetype="image/png")

# ▶️ Run server
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
