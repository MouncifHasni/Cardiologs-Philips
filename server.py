from flask import Flask, request, jsonify
import pandas as pd
from datetime import datetime, timedelta

app = Flask(__name__)

@app.route('/delineation', methods=['POST'])
def process_ecg():
    # Check if file is part of the request
    if 'file' not in request.files:
        return jsonify({'error': "Missing file parameter"}), 400
    
    # Retrieve the file from the request
    file = request.files['file']
    # get the provided datetime from the request here for the test i will use datetime.now()
    provided_datetime = request.form.get('start_datetime', None)
    if provided_datetime:
        start_datetime = datetime.strptime(provided_datetime, '%Y-%m-%d %H:%M:%S')
    else:
        start_datetime = datetime.now()

    try:
        #read data
        df = pd.read_csv(file, header=None, names=['Wave type', 'Wave onset', 'Wave offset', 'Tag 1', 'Tag 2'],usecols=[0, 1, 2, 3, 4],
                        on_bad_lines='skip')

        # combine the last two tag columns into one 'Wave tags' column
        df['Tag 1'] = df['Tag 1'].fillna('')
        df['Tag 2'] = df['Tag 2'].fillna('')
        df['Wave tags'] = df.apply(lambda row: row['Tag 1'] + (',' + row['Tag 2'] if row['Tag 1'] and row['Tag 2'] else row['Tag 2']), axis=1)
    except pd.errors.ParserError as e:
        return jsonify({'error': "Error processing file."}), 500

    # Calculate the premature counts for P waves and QRS complexes
    premature_p_count = df[(df['Wave type'] == 'P') & (df['Wave tags'].str.contains('premature', na=False))].shape[0]
    premature_qrs_count = df[(df['Wave type'] == 'QRS') & (df['Wave tags'].str.contains('premature', na=False))].shape[0]

    # Extract heart rates
    qrs_times = df[df['Wave type'] == 'QRS']['Wave onset']
    if qrs_times.empty:
        return jsonify({
            'error': "No QRS found in the data."
        }), 400

    intervals = qrs_times.diff().dropna() / 1000.0  # convert ms to seconds
    if intervals.empty:
        return jsonify({
            'error': "Not enough QRS to compute heart rate intervals."
        }), 400
    
    heart_rates = 60 / intervals  # beats per minute

    try:
        mean_heart_rate = float(heart_rates.mean())
        min_heart_rate, min_index = float(heart_rates.min()), heart_rates.idxmin()
        max_heart_rate, max_index = float(heart_rates.max()), heart_rates.idxmax() 
        min_time = start_datetime + timedelta(seconds=qrs_times[min_index] / 1000)
        max_time = start_datetime + timedelta(seconds=qrs_times[max_index] / 1000)

    except IndexError as e:
        return jsonify({
            'error': "Error calculating time indices for heart rates.",
        }), 400

    response = {
        'Premature P Count': premature_p_count,
        'Premature QRS Count': premature_qrs_count,
        'Mean Heart Rate (bpm)': mean_heart_rate,
        'Min Heart Rate (bpm)': min_heart_rate,
        'Min Heart Rate Time': min_time.strftime('%Y-%m-%d %H:%M:%S'),
        'Max Heart Rate (bpm)': max_heart_rate,
        'Max Heart Rate Time': max_time.strftime('%Y-%m-%d %H:%M:%S')
    }

    return jsonify(response)

if __name__ == '__main__':
    app.run(debug=True)
