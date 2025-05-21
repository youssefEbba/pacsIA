from flask import Flask, request, jsonify
import requests
import os
import google.generativeai as genai

app = Flask(__name__)

# Base PACS API URL
BASE_URL = "http://94.130.160.188:8080/dcm4chee-arc/aets/DCM4CHEE/rs"

# Configure Gemini
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel("gemini-pro")

# Get first SeriesInstanceUID
def get_first_series(study_uid):
    url = f"{BASE_URL}/studies/{study_uid}/series"
    response = requests.get(url, headers={"Accept": "application/dicom+json"})
    if response.status_code != 200:
        raise Exception(f"Failed to fetch series: {response.status_code}")
    series_list = response.json()
    if not series_list:
        raise Exception("No series found in study")
    return series_list[0]['0020000E']['Value'][0]

# Get first SOPInstanceUID
def get_first_instance(study_uid, series_uid):
    url = f"{BASE_URL}/studies/{study_uid}/series/{series_uid}/instances"
    response = requests.get(url, headers={"Accept": "application/dicom+json"})
    if response.status_code != 200:
        raise Exception(f"Failed to fetch instances: {response.status_code}")
    instances = response.json()
    if not instances:
        raise Exception("No instances found in series")
    return instances[0]['00080018']['Value'][0]

# Download DICOM (optional if you want to analyze image later)
def download_dicom_file(study_uid, series_uid, instance_uid, save_path):
    file_url = f"{BASE_URL}/studies/{study_uid}/series/{series_uid}/instances/{instance_uid}"
    headers = {"Accept": "*/*"}
    response = requests.get(file_url, headers=headers)
    if response.status_code == 200:
        with open(save_path, "wb") as f:
            f.write(response.content)
        return save_path
    else:
        raise Exception(f"Failed to download DICOM file: {response.status_code}")

# Get interpretation from Gemini in French
def interpret_with_gemini(instance_uid):
    prompt = f"""Je vous fournis l'identifiant d'une instance DICOM : {instance_uid}.
Veuillez fournir une interprétation médicale possible de cette image basée sur cet identifiant.
Faites comme si vous étiez un radiologue. Répondez en français."""
    
    response = model.generate_content(prompt)
    return response.text

@app.route('/process-dicom', methods=['POST'])
def process_dicom():
    data = request.get_json()
    if not data or 'dicom_url' not in data:
        return jsonify({"error": "Missing dicom_url in request"}), 400

    dicom_url = data['dicom_url']

    try:
        study_uid = dicom_url.rstrip('/').split('/')[-1]
    except Exception:
        return jsonify({"error": "Invalid dicom_url format"}), 400

    try:
        series_uid = get_first_series(study_uid)
        instance_uid = get_first_instance(study_uid, series_uid)

        # Optional download
        save_path = f"/tmp/{instance_uid}.dcm"
        download_dicom_file(study_uid, series_uid, instance_uid, save_path)

        # Interpret using Gemini (in French)
        interpretation = interpret_with_gemini(instance_uid)

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
    app.run(host='0.0.0.0', port=5000)
