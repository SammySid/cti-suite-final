import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'backend'))
from report_service import generate_pdf_report

def main():
    payload = {
        "client": "DHARIWAL INFRASTRUCTURE LTD CHANDRAPUR",
        "asset": "CT - 02 , CELL 02",
        "test_date": "27 March 2026",
        "report_date": "15 April 2026",
        "preamble_paragraphs": [
            "Due to poor performance of the cooling tower, factors influencing the poor performance were identified to be progressively resolved. To carry out this procedure it was decided to carry out the changes on one cell and based on the result carry out the same on balance cell. Accordingly one cell was isolated and water from the cell was collected at both ends and the temperature of the collected water was measured. This procedure had to be conducted both before change of gear box and fan and post change of gear box and fan ( running at higher power ) to ascertain the effect on cold water temperature on one single cell so that the same could be replicated in other cells.",
            "Accordingly on 23 of September 2025, Pre upgrade test was carried out. testing team reached site and carried out collection of data from 4 to 8 pm . ( stabilized peak load was available at 4 .0 pm and hence stable readings from 5 to 9 pm was collected. Most stable 1 hour readings are taken up for assessment / benchmarking to be compared with post gearbox and fan replacement measurements.",
            "The existing Maya fan was replaced with another fan and new gear box of higher rating. The fan was operated at 116 kw. Based on these conditions a single cell Post change test was carried out on cell no 2 in exactly the similar manner to the pre test so that the improvement in the cell can be calculated. The test was carried out on 6th October 2025 from 5 to 9 pm",
            "Subsequently distribution system modifications were made and test was conducted on 27 March 2026 in a single isolated cell to understand effect of these changes."
        ],
        "members_client": [
            "Mr Shrikant Shrivastava ( Remote)",
            "Mr GAURAV HANTODKAR",
            "Mr PAWAN GAWANDE"
        ],
        "members_ssctc": [
            "Mr SURESH SARMA",
            "Mr SANJAY GORAD",
            "Mr MRADUL VISHWAKARMA",
            "Mr PARAG VISHWAKARMA",
            "Mr RAHUL MANKE"
        ],
        "assessment_method": [
            "Pre test was conducted on 27 March 2026.",
            "Cell no 2 has been isolated at the basin level for collection of cold water directly from the rain zone by providing sheets of frp placed on structural members at the top of the basin so as to collect water from the rain zone and move the water by slope towards the drums placed on either air inlet.",
            "Similarly on 6th October 2025 Post fan and gear box change test was conducted exactly in line with the pre test methods.",
            "Since 2 different set of conditions have to be evaluated, there has to be a reference to which both these test collected data can be compared to. This base we have taken as the design conditions."
        ],
        "instrument_placement": [
            "Air flow was measured using Data Logging anemometer, manually generally as per CTI ATC 143 Method of equal area.. Totally 10 traverse were taken in each quadrant thus total of 40 readings were taken for the one fan.",
            "Hot water – was taken at inlet of the hot water to the cooling tower which is common for all cells.",
            "Cold water – As water was collected using a sheets supported on structure and leading the water to drums placed at either air inlet side. 12 sensors were placed on side A and 12 sensors were placed on side B. thus 24 sensors were used.",
            "Water flow – was measured using UFM ( GE Make ) on the riser.",
            "WBT ( inlet ) -was measured on either side of the air inlet using wet bulb automatic stations."
        ],
        "conclusions": [
            "Ms Dhariwal Infrastructure Ltd – Chandrapur, had been experiencing shortfall in cooling tower performance.",
            "Cooling Tower Performance test conducted on cooling tower CT2 in March 2025 showed 5.7 deg C cwt deviation – as per procedure – CTI ATC 105 By SSCTC",
            "Subsequently since Fan performance was identified as one reason for performance shortfall, the fan was changed to original fan and a test was conducted which was referred to as Post fan replacement single cell test. Large improvement was observed to about 1.5 deg C which was toned down to about 0.7 deg C considering various uncertainties in the system.",
            "Testing of the cell was carried out after incorporating the distribution system changes on 27th of March 2026. The additional head available in the system caused flow to increase substantially in the cell. Even under these conditions the cell showed an improvement in performance of approx. 0.5 deg C above the post fan modification test."
        ],
        "suggestions": [
            "With 3 pumps operating and one cell under higher flow velocities through the duct would be higher by 1.23% this would naturally cause a higher static pressure at the back end. To mitigate this one sizer lower ferrul ( orifice ) can be provided at the last 3 pipes of the cell away from the riser.",
            "Providing a vertical barrier near the water collection location to reduce the effect of water velocity and thus turbulence at point of measurement."
        ],
        "final_data_table": [
            {"name": "Water Flow", "unit": "M3/hr", "test1": "2998", "test2": "3067.21", "test3": "3680"},
            {"name": "WBT", "unit": "Deg.C", "test1": "25.25", "test2": "24.22", "test3": "21.7"},
            {"name": "HWT", "unit": "Deg.C", "test1": "44.67", "test2": "43.21", "test3": "42.13"},
            {"name": "CWT", "unit": "Deg.C", "test1": "35.08", "test2": "32.89", "test3": "32.4"},
            {"name": "Fan Power At Motor Inlet", "unit": "KW", "test1": "97.04", "test2": "116.24", "test3": "117"},
            {"name": "Fan Air Flow", "unit": "M3/s", "test1": "405.97", "test2": "499", "test3": "485"},
            {"name": "Range", "unit": "Deg.C", "test1": "9.59", "test2": "10.32", "test3": "9.73"}
        ],
        "data_notes": [
            "Improvement of 1.5 appears high in \"TEST 2\" so we consider that as 0.7 Deg C",
            "single cell isolated testing involves UNCERAINITY in measurement due to turbulent water flow",
            "during the TEST 3 Water flow was 23% higher, for splash bars the performance at Highwer water decreases rapidly."
        ],
        "airflow": {
            "avg_velocity": "4.99",
            "area": "92.25",
            "total_flow": "459.84"
        },
        "intersect": {
            "f90_flow": "3477", "f90_cwt": "27.84",
            "f100_flow": "3864", "f100_cwt": "28.83",
            "f110_flow": "4250", "f110_cwt": "30.21"
        },
        "math_results": {
            "adj_flow": "3720.91",
            "pred_cwt": "28.62",
            "test_cwt": "32.40",
            "shortfall": "3.83",
            "capability": "74.8"
        },
        "test_range": 9.73
    }

    try:
        print("Starting MASSIVE PDF generation...")
        pdf_bytes = generate_pdf_report(payload)
        
        output_file = os.path.join(os.path.dirname(__file__), "temp", "Dhariwal_Auto_Generated.pdf")
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        
        with open(output_file, "wb") as f:
            f.write(pdf_bytes)
            
        print(f"✅ Success! PDF generated internally at: {output_file}")
        print(f"File size: {len(pdf_bytes)} bytes.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"❌ Failed to generate PDF: {e}")

if __name__ == '__main__':
    main()
