from openai_client import client, MODEL2

def categorize_menu_language(menu_language):
    prompt = f"""
    Based on the input '{menu_language}', categorize it as one of the following:
    - 'En' for English
    - 'Pt' for Portuguese
    - 'Fr' for French
    - 'De' for German
    - 'Es' for Spanish
    If it doesn't match any, return 'None'.
    Return only the code.
    """
    response = client.chat.completions.create(
        model=MODEL2,
        messages=[
            {"role": "system", "content": "You classify the language."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )
    return response.choices[0].message.content.strip()

language_map = {
    "Inglês Britânico": "En",
    "Português Europeu": "Pt",
    "Francês Europeu": "Fr",
    "Alemão (Alemanha)": "De",
    "Espanhol Europeu": "Es"
} 