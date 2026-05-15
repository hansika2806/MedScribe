from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


PDF_DIR = Path(__file__).parent / "pdfs"
PDF_DIR.mkdir(parents=True, exist_ok=True)


REPORTS = [
    {
        "filename": "general_medicine_report.pdf",
        "patient": "Adult, 45 years",
        "doctor": "Dr. Meera Rao",
        "section": "GENERAL MEDICINE PANEL",
        "values": [
            ("HbA1c", "8.2", "4.0 - 5.6", "%"),
            ("Fasting Blood Glucose", "185", "70 - 100", "mg/dL"),
            ("Total Cholesterol", "220", "< 200", "mg/dL"),
            ("HDL", "42", "> 40", "mg/dL"),
            ("LDL", "145", "< 130", "mg/dL"),
            ("Triglycerides", "165", "< 150", "mg/dL"),
            ("Creatinine", "1.1", "0.7 - 1.2", "mg/dL"),
            ("Hemoglobin", "13.2", "13.0 - 17.0", "g/dL"),
        ],
    },
    {
        "filename": "cardiology_report.pdf",
        "patient": "Adult, 58 years",
        "doctor": "Dr. Arvind Menon",
        "section": "CARDIAC RISK PANEL",
        "values": [
            ("Troponin I", "0.02", "< 0.01", "ng/mL"),
            ("CK-MB", "15", "0 - 24", "U/L"),
            ("Total Cholesterol", "265", "< 200", "mg/dL"),
            ("HDL", "38", "> 40", "mg/dL"),
            ("LDL", "185", "< 130", "mg/dL"),
            ("Triglycerides", "210", "< 150", "mg/dL"),
            ("Blood Glucose", "142", "70 - 140", "mg/dL"),
            ("Sodium", "138", "135 - 145", "mEq/L"),
            ("Potassium", "4.2", "3.5 - 5.0", "mEq/L"),
        ],
    },
    {
        "filename": "endocrinology_report.pdf",
        "patient": "Adult, 38 years",
        "doctor": "Dr. Kavita Sharma",
        "section": "ENDOCRINOLOGY PANEL",
        "values": [
            ("HbA1c", "9.8", "4.0 - 5.6", "%"),
            ("Fasting Blood Glucose", "245", "70 - 100", "mg/dL"),
            ("Post Prandial Blood Glucose", "320", "< 140", "mg/dL"),
            ("TSH", "8.5", "0.4 - 4.0", "mIU/L"),
            ("Free T4", "0.7", "0.8 - 1.8", "ng/dL"),
            ("Insulin Fasting", "18", "2 - 20", "uIU/mL"),
            ("Creatinine", "0.9", "0.7 - 1.2", "mg/dL"),
            ("eGFR", "88", "> 60", "mL/min"),
        ],
    },
    {
        "filename": "pediatrics_report.pdf",
        "patient": "Child, 12 years",
        "doctor": "Dr. Nisha Iyer",
        "section": "PEDIATRIC DIABETES PANEL",
        "values": [
            ("HbA1c", "8.9", "4.0 - 5.6", "%"),
            ("Fasting Blood Glucose", "195", "70 - 100", "mg/dL"),
            ("Hemoglobin", "11.8", "12.0 - 15.0", "g/dL"),
            ("WBC", "8500", "4000 - 11000", "cells/uL"),
            ("Platelets", "285000", "150000 - 450000", "cells/uL"),
            ("Creatinine", "0.6", "0.5 - 1.0", "mg/dL"),
            ("Sodium", "137", "135 - 145", "mEq/L"),
            ("Potassium", "3.9", "3.5 - 5.0", "mEq/L"),
        ],
    },
    {
        "filename": "respiratory_report.pdf",
        "patient": "Adult, 52 years",
        "doctor": "Dr. Farhan Ali",
        "section": "RESPIRATORY INFECTION PANEL",
        "values": [
            ("WBC", "14500", "4000 - 11000", "cells/uL"),
            ("Neutrophils", "82", "40 - 70", "%"),
            ("CRP", "45", "< 5", "mg/L"),
            ("ESR", "65", "0 - 20", "mm/hr"),
            ("Hemoglobin", "11.2", "13.0 - 17.0", "g/dL"),
            ("Procalcitonin", "0.8", "< 0.1", "ng/mL"),
            ("Sodium", "134", "135 - 145", "mEq/L"),
            ("Potassium", "3.6", "3.5 - 5.0", "mEq/L"),
        ],
    },
]


def build_report(report: dict):
    output_path = PDF_DIR / report["filename"]
    doc = SimpleDocTemplate(str(output_path), pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("City General Hospital", styles["Title"]))
    story.append(Paragraph("Department of Laboratory Medicine", styles["Heading2"]))
    story.append(Spacer(1, 12))

    patient_data = [
        ["Patient Name", "Test Patient"],
        ["Patient Details", report["patient"]],
        ["Report Date", "15-May-2026"],
        ["Doctor Name", report["doctor"]],
        ["Lab Ref No", f"CGH-2026-{report['filename'][:3].upper()}"],
    ]
    patient_table = Table(patient_data, colWidths=[140, 330])
    patient_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(patient_table)
    story.append(Spacer(1, 18))
    story.append(Paragraph(report["section"], styles["Heading3"]))

    lab_data = [["Test Name", "Result", "Reference Range", "Units"]]
    lab_data.extend(report["values"])
    lab_table = Table(lab_data, colWidths=[190, 80, 130, 80])
    lab_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.darkgreen),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.94, 0.97, 0.94)]),
        ("GRID", (0, 0), (-1, -1), 0.7, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(lab_table)
    story.append(Spacer(1, 22))
    story.append(Paragraph("Lab Technician Signature: Verified Electronically", styles["Normal"]))
    story.append(Paragraph("This report is intended for physician review.", styles["Italic"]))

    doc.build(story)
    print(f"Created {output_path}")


def main():
    for report in REPORTS:
        build_report(report)


if __name__ == "__main__":
    main()
