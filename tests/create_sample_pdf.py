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


def create_sample_report():
    doc = SimpleDocTemplate(
        str(PDF_DIR / "sample_lab_report.pdf"),
        pagesize=A4,
    )

    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("CITY GENERAL HOSPITAL", styles["Title"]))
    story.append(Paragraph("Laboratory Investigation Report", styles["Heading2"]))
    story.append(Spacer(1, 12))

    patient_data = [
        ["Patient Name:", "Test Patient"],
        ["Age / Sex:", "45 Years / Male"],
        ["Date:", "15-May-2026"],
        ["Doctor:", "Dr. Test Physician"],
        ["Ref No:", "LAB-2026-001"],
    ]
    patient_table = Table(patient_data, colWidths=[150, 300])
    story.append(patient_table)
    story.append(Spacer(1, 20))

    story.append(Paragraph("BIOCHEMISTRY RESULTS", styles["Heading3"]))

    lab_data = [
        ["Test", "Result", "Reference Range", "Units"],
        ["HbA1c", "8.2", "4.0 - 5.6", "%"],
        ["Fasting Blood Glucose", "185", "70 - 100", "mg/dL"],
        ["Post Prandial Glucose", "245", "< 140", "mg/dL"],
        ["Total Cholesterol", "220", "< 200", "mg/dL"],
        ["HDL Cholesterol", "42", "> 40", "mg/dL"],
        ["LDL Cholesterol", "145", "< 130", "mg/dL"],
        ["Triglycerides", "165", "< 150", "mg/dL"],
        ["Serum Creatinine", "1.1", "0.7 - 1.2", "mg/dL"],
        ["Blood Urea", "32", "15 - 40", "mg/dL"],
        ["Haemoglobin", "13.2", "13.0 - 17.0", "g/dL"],
        ["Sodium", "138", "135 - 145", "mEq/L"],
        ["Potassium", "4.1", "3.5 - 5.0", "mEq/L"],
    ]

    lab_table = Table(lab_data, colWidths=[180, 80, 130, 80])
    lab_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
    ]))

    story.append(lab_table)
    story.append(Spacer(1, 20))
    story.append(Paragraph("Authorized Signatory: Lab Technician", styles["Normal"]))

    doc.build(story)
    print("Sample PDF created: tests/pdfs/sample_lab_report.pdf")


if __name__ == "__main__":
    create_sample_report()
