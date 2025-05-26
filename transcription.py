import pandas as pd
from openai_client import client, MODEL
from file_utils import encode_image_pil

def process_image_to_excel(images, menu_language):
    df = pd.DataFrame(columns=[
        'CategoryTitleDefault', 'SubcategoryTitleDefault', 'ItemNameDefault', 'ItemDescriptionDefault',
        'ItemPrice'
    ])

    system_prompt = f"""
    Your goal is to convert the menu image to a structured table with columns:
- CategoryTitleDefault (Column A) - Category Title: The default category title displayed on your menu (text, max 40 characters).
- SubcategoryTitleDefault  (Column B) - Subcategory Title (Optional): Subcategory titles displayed on your menu (text, max 40 characters).
- ItemNameDefault (Column C) - Item Name : The default item name displayed on your menu (text, max 40 characters).
- ItemDescriptionDefault (Column D) - Item Description (Optional): The default item description displayed on your menu (text, max 120 characters).
- ItemPrice (Column E) - Item Price: Price of each item (Text). Remove currency symbols and only include numbers (example of formats: 9.99 or 9.9 or 9 or 9,99 or 9,9 or 9)

The menu language is {menu_language}.

Output in Markdown table format:
| CategoryTitleDefault | SubcategoryTitleDefault | ItemNameDefault | ItemDescriptionDefault | ItemPrice |
    """

    headers_added = False
    for img in images:
        base64_image = encode_image_pil(img)
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",
                 "content": [
                     {"type": "text", "text": "Convert this menu image to a structured Excel sheet format."},
                     {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                 ]
                }
            ],
            temperature=0
        )

        menu_data = response.choices[0].message.content.split('\n')
        for row in menu_data:
            if row.startswith('|') and not row.startswith('|-'):
                columns = [col.strip() for col in row.split('|')[1:-1]]
                if 'CategoryTitleDefault' in columns:
                    if not headers_added:
                        headers_added = True
                    else:
                        continue
                    continue

                if len(columns) == len(df.columns):
                    df.loc[len(df)] = columns

    required_columns = [
        'CategoryTitleDefault', 'SubcategoryTitleDefault', 'ItemNameDefault', 'ItemDescriptionDefault',
        'ItemPrice',
        'CategoryTitleEn', 'SubcategoryTitleEn', 'ItemNameEn', 'ItemDescriptionEn',
        'CategoryTitlePt', 'SubcategoryTitlePt', 'ItemNamePt', 'ItemDescriptionPt',
        'CategoryTitleFr', 'SubcategoryTitleFr', 'ItemNameFr', 'ItemDescriptionFr',
        'CategoryTitleDe', 'SubcategoryTitleDe', 'ItemNameDe', 'ItemDescriptionDe',
        'CategoryTitleEs', 'SubcategoryTitleEs', 'ItemNameEs', 'ItemDescriptionEs'
    ]
    for column in required_columns:
        if column not in df.columns:
            df[column] = ""

    return df 