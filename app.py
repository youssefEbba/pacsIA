from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Base PACS API URL (adjust if needed)
BASE_URL = "http://94.130.160.188:8080/dcm4chee-arc/aets/DCM4CHEE/rs"

def get_first_series(study_uid):
    url = f"{BASE_URL}/studies/{study_uid}/series"
    # Use Accept header application/dicom+json to avoid 406
    response = requests.get(url, headers={"Accept": "application/dicom+json"})
    if response.status_code != 200:
        raise Exception(f"Failed to fetch series: {response.status_code}")
    series_list = response.json()
    if not series_list:
        raise Exception("No series found in study")
    # Depending on your PACS JSON structure, this may need adjusting
    return series_list[0]['0020000E']['Value'][0]  # SeriesInstanceUID

def get_first_instance(study_uid, series_uid):
    url = f"{BASE_URL}/studies/{study_uid}/series/{series_uid}/instances"
    response = requests.get(url, headers={"Accept": "application/dicom+json"})
    if response.status_code != 200:
        raise Exception(f"Failed to fetch instances: {response.status_code}")
    instances = response.json()
    if not instances:
        raise Exception("No instances found in series")
    return instances[0]['00080018']['Value'][0]  # SOPInstanceUID

def download_dicom_file(study_uid, series_uid, instance_uid, save_path):
    # Note the added /file at the end for actual DICOM file download
    file_url = f"{BASE_URL}/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}"
    # Use Accept header application/dicom to avoid 406
    print(f"Downloading DICOM file from {file_url}")
    headers = {"Accept": "application/dicom; transfer-syntax=*"}
    response = requests.get(file_url, headers=headers)
    if response.status_code == 200:
        with open(save_path, "wb") as f:
            f.write(response.content)
        return save_path
    else:
        raise Exception(f"Failed to download DICOM file: {response.status_code}")

@app.route('/process-dicom', methods=['POST'])
def process_dicom():
    data = request.get_json()
    if not data or 'dicom_url' not in data:
        return jsonify({"error": "Missing dicom_url in request"}), 400

    dicom_url = data['dicom_url']

    # Extract Study Instance UID from URL
    # Example URL: http://.../studies/{studyUID}
    try:
        study_uid = dicom_url.rstrip('/').split('/')[-1]
    except Exception:
        return jsonify({"error": "Invalid dicom_url format"}), 400

    try:
        series_uid = get_first_series(study_uid)
        instance_uid = get_first_instance(study_uid, series_uid)
        save_path = f"/tmp/{instance_uid}.dcm"
        download_dicom_file(study_uid, series_uid, instance_uid, save_path)

        # Dummy interpretation - replace with your AI model call
        interpretation = f"Interpretation of DICOM instance {instance_uid}"

        # Optionally remove the file after processing
        if os.path.exists(save_path):
            os.remove(save_path)

        return jsonify({
            "study_uid": study_uid,
            "series_uid": series_uid,
            "instance_uid": instance_uid,
            "interpretation": interpretation
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Run on all interfaces, port 5000
    app.run(host='0.0.0.0', port=5000)
