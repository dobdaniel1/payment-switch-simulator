RESPONSE_MESSAGES = {
    "00": "Approved",
    "05": "Do not honour",
    "14": "Invalid card number",
    "51": "Insufficient funds",
    "54": "Expired card",
    "61": "Exceeds withdrawal amount limit",
    "91": "Issuer or switch inoperative",
    "92": "No route to issuer",
}


def message_for(code: str) -> str:
    return RESPONSE_MESSAGES.get(code, "Unknown")
