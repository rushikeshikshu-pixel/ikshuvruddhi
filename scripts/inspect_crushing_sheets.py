import pandas as pd

excel_path = r"C:/Users/rishi/.gemini/antigravity/brain/1e85251f-10b8-450e-b775-c156e2482133/.user_uploaded/media_1793113508465_c5467fc6.xlsx"
xl = pd.ExcelFile(excel_path)
print("Sheets found:", xl.sheet_names)

df25 = xl.parse("25.10.2026")
df26 = xl.parse("26.10.2026")

print("25 Oct shape:", df25.shape, "Total Net Wt:", df25["NET_WT"].sum(), "Unique plots:", df25["DOCUMENT_NO"].nunique())
print("26 Oct shape:", df26.shape, "Total Net Wt:", df26["NET_WT"].sum(), "Unique plots:", df26["DOCUMENT_NO"].nunique())

df_combined = pd.concat([df25, df26], ignore_index=True)
print("Combined shape:", df_combined.shape)
print("Total Net Wt:", df_combined["NET_WT"].sum())
print("Unique DOCUMENT_NO:", df_combined["DOCUMENT_NO"].nunique())
print("Columns:", df_combined.columns.tolist())
print(df_combined.head(5))
