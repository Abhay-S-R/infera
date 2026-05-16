from fpdf import FPDF
import markdown

text = """
## Executive Summary
This is a **test** of the *markdown* conversion.
"""

pdf = FPDF()
pdf.add_page()
html = markdown.markdown(text)
pdf.write_html(html)
pdf.output("test.pdf")
print("Done")
