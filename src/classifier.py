"""
EdgeDB: On-Device Expense Classifier
Lightweight local NLP categorization running on edge devices before sync.
"""

import re

CATEGORY_KEYWORDS = {
    "Food & Dining": [
        "coffee", "tea", "cafe", "starbucks", "blue tokai", "burger", "pizza", "lunch", "dinner",
        "breakfast", "swiggy", "zomato", "restaurant", "groceries", "supermarket", "snacks", "barista"
    ],
    "Travel & Transit": [
        "uber", "ola", "rapido", "cab", "auto", "train", "metro", "flight", "indigo", "bus", "fuel",
        "petrol", "diesel", "parking", "toll", "fare", "railway"
    ],
    "Electronics & Tech": [
        "laptop", "mouse", "keyboard", "monitor", "cable", "usb", "github", "aws", "gcp", "azure",
        "chatgpt", "openai", "copilot", "domain", "hosting", "ram", "ssd", "charger"
    ],
    "Utilities & Bills": [
        "wifi", "broadband", "jio", "airtel", "electricity", "water", "gas", "recharge", "phone bill",
        "maintenance", "rent"
    ],
    "Health & Fitness": [
        "gym", "pharmacy", "medicine", "doctor", "hospital", "clinic", "whey", "protein", "vitamins",
        "band", "dumbbells", "yoga"
    ],
    "Books & Education": [
        "book", "textbook", "novel", "coursera", "udemy", "exam", "course", "stationery", "pen",
        "notebook", "korth", "database concepts", "tuition", "library"
    ]
}

def classify_expense(description: str):
    """
    Given a short text description of an expense, returns:
    (predicted_category_name, confidence_score)
    """
    if not description:
        return "Food & Dining", 0.7000

    text_lower = description.lower()
    best_category = "Food & Dining"
    best_score = 0.50

    for category, keywords in CATEGORY_KEYWORDS.items():
        matches = 0
        for kw in keywords:
            if re.search(r'\b' + re.escape(kw) + r'\b', text_lower):
                matches += 1
        if matches > 0:
            score = min(0.85 + (matches * 0.05), 0.99)
            if score > best_score:
                best_score = score
                best_category = category

    # Default fallback if no keyword matches
    if best_score == 0.50:
        best_score = 0.7500
        best_category = "Utilities & Bills"

    return best_category, round(best_score, 4)

if __name__ == "__main__":
    test_cases = [
        "Cold brew coffee at cafe",
        "Uber ride to station",
        "Korth Database textbook",
        "AWS cloud hosting bill",
        "Gym subscription for October"
    ]
    for desc in test_cases:
        cat, conf = classify_expense(desc)
        print(f"'{desc}' -> {cat} (Confidence: {conf})")

