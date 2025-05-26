import pandas as pd
from openai_client import client, MODEL2
from language_utils import language_map

translation_cache = {}

def translate_text(text, src_lang_code, tgt_lang_code):
    cache_key = (text, tgt_lang_code)
    if cache_key in translation_cache:
        return translation_cache[cache_key]

    system_prompt = f"You are a translator for a restaurant. Assume the intended meaning is restaurant vocabulary. Translate from {src_lang_code} to {tgt_lang_code}. Return only the translated text. Presume the intent of the user and understand if it requires translations or it should be kept in its original language."
    user_prompt = f"Translate this text:\n{text}"

    response = client.chat.completions.create(
        model=MODEL2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.0
    )
    translated_text = response.choices[0].message.content.strip()
    translation_cache[cache_key] = translated_text
    return translated_text

def fill_translations(df, menu_language):
    src_code = language_map[menu_language]
    target_langs = [lang for lang in language_map.values() if lang != src_code]

    translation_columns = {
        'CategoryTitleDefault': ['CategoryTitleEn', 'CategoryTitlePt', 'CategoryTitleFr', 'CategoryTitleDe', 'CategoryTitleEs'],
        'SubcategoryTitleDefault': ['SubcategoryTitleEn', 'SubcategoryTitlePt', 'SubcategoryTitleFr', 'SubcategoryTitleDe', 'SubcategoryTitleEs'],
        'ItemNameDefault': ['ItemNameEn', 'ItemNamePt', 'ItemNameFr', 'ItemNameDe', 'ItemNameEs'],
        'ItemDescriptionDefault': ['ItemDescriptionEn', 'ItemDescriptionPt', 'ItemDescriptionFr', 'ItemDescriptionDe', 'ItemDescriptionEs']
    }

    code_to_full = {'En': 'English', 'Pt': 'Portuguese', 'Fr': 'French', 'De': 'German', 'Es': 'Spanish'}

    for index, row in df.iterrows():
        for default_col, target_cols in translation_columns.items():
            if row[default_col] and str(row[default_col]).strip():
                for tgt_col, tgt_code in zip(target_cols, ['En', 'Pt', 'Fr', 'De', 'Es']):
                    if tgt_code != src_code and (pd.isna(row[tgt_col]) or not str(row[tgt_col]).strip()):
                        translated = translate_text(str(row[default_col]), code_to_full[src_code], code_to_full[tgt_code])
                        df.at[index, tgt_col] = translated 