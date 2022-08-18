# translation table for curly/typograghic single and double quotes
smart_quote_conversion = str.maketrans(
    {
        "’": "'",
        "‘": "'",
        "”": '"',
        "“": '"',
    }
)


def simplify_quotes(text):
    """convert typographic quotes to single quotes (double or single)"""
    return text.translate(smart_quote_conversion)
