"""Deterministic sample content for the unauthenticated guided demo."""


GUIDED_DEMO_DOCUMENT_A = """Student Travel Reimbursement Policy

Students may receive up to $300 per trip for approved club travel.
Written approval from the faculty advisor is required before booking.
Itemized receipts must be submitted within 10 calendar days after returning.
Personal vehicle mileage is reimbursed at $0.50 per mile.
"""

GUIDED_DEMO_DOCUMENT_B = """Updated Student Travel Reimbursement Policy

Students may receive up to $450 per trip for approved club travel.
Written approval from both the faculty advisor and the treasurer is required before booking.
Itemized receipts must be submitted within 30 calendar days after returning.
Personal vehicle mileage is reimbursed at $0.67 per mile.
Airfare upgrades are not eligible for reimbursement.
"""


def get_guided_demo() -> dict:
    """Return a fresh sample comparison and its matching source documents."""

    return {
        "document_a_name": "Travel Policy (Original).txt",
        "document_b_name": "Travel Policy (Updated).txt",
        "document_a_text": GUIDED_DEMO_DOCUMENT_A,
        "document_b_text": GUIDED_DEMO_DOCUMENT_B,
        "comparison_result": {
            "document_a_summary": (
                "The original policy reimburses approved student club travel "
                "up to $300 per trip, with faculty-advisor approval, a 10-day "
                "receipt deadline, and mileage reimbursement of $0.50 per mile."
            ),
            "document_b_summary": (
                "The updated policy raises the travel cap to $450, requires "
                "faculty-advisor and treasurer approval, extends the receipt "
                "deadline to 30 days, raises mileage reimbursement to $0.67 "
                "per mile, and excludes airfare upgrades."
            ),
            "similarities": [
                "Both policies cover approved student club travel.",
                "Both require written approval before booking.",
                "Both reimburse personal vehicle mileage and require itemized receipts.",
            ],
            "differences": [
                {
                    "title": "Per-trip reimbursement cap",
                    "category": "Change",
                    "severity": "Medium",
                    "description": "The maximum reimbursement increases by $150 per trip.",
                    "document_a": "$300 per trip",
                    "document_b": "$450 per trip",
                },
                {
                    "title": "Approval requirements",
                    "category": "Addition",
                    "severity": "High",
                    "description": "The updated policy adds treasurer approval before booking.",
                    "document_a": "Written approval from the faculty advisor",
                    "document_b": "Written approval from both the faculty advisor and the treasurer",
                },
                {
                    "title": "Receipt submission deadline",
                    "category": "Change",
                    "severity": "Medium",
                    "description": "The submission window is extended by 20 calendar days.",
                    "document_a": "Within 10 calendar days after returning",
                    "document_b": "Within 30 calendar days after returning",
                },
                {
                    "title": "Mileage reimbursement rate",
                    "category": "Change",
                    "severity": "Low",
                    "description": "The reimbursement rate increases by $0.17 per mile.",
                    "document_a": "$0.50 per mile",
                    "document_b": "$0.67 per mile",
                },
                {
                    "title": "Airfare upgrades",
                    "category": "Addition",
                    "severity": "Low",
                    "description": "The updated policy explicitly excludes airfare upgrades.",
                    "document_a": "Not found in the provided text.",
                    "document_b": "Airfare upgrades are not eligible for reimbursement.",
                },
            ],
            "key_details": [
                {
                    "field": "Maximum reimbursement per trip",
                    "document_a": "$300",
                    "document_b": "$450",
                },
                {
                    "field": "Approval before booking",
                    "document_a": "Faculty advisor",
                    "document_b": "Faculty advisor and treasurer",
                },
                {
                    "field": "Receipt deadline after returning",
                    "document_a": "10 calendar days",
                    "document_b": "30 calendar days",
                },
                {
                    "field": "Mileage reimbursement rate",
                    "document_a": "$0.50 per mile",
                    "document_b": "$0.67 per mile",
                },
            ],
            "overall_conclusion": (
                "The updated policy increases reimbursement limits and "
                "submission flexibility, while adding an approval step and "
                "explicitly excluding airfare upgrades. Travelers should "
                "confirm both approvals before booking."
            ),
            "limitations": [
                "This sample demonstrates the comparison interface; it is not an AI-generated review.",
                "The sample does not include other travel rules or supporting procedures.",
            ],
            "risk_flags": [
                "Missing treasurer approval could make a booking ineligible under the updated policy.",
                "Airfare upgrades are now expressly excluded from reimbursement.",
            ],
            "deadlines": [
                "Updated policy: submit itemized receipts within 30 calendar days after returning.",
                "Obtain written approval from both required approvers before booking.",
            ],
            "source_citations": [
                {
                    "finding": "The per-trip reimbursement cap increased.",
                    "quote": "Students may receive up to $300 per trip",
                    "source": "Document A",
                },
                {
                    "finding": "The per-trip reimbursement cap increased.",
                    "quote": "Students may receive up to $450 per trip",
                    "source": "Document B",
                },
                {
                    "finding": "Treasurer approval is now required before booking.",
                    "quote": "Written approval from both the faculty advisor and the treasurer is required before booking.",
                    "source": "Document B",
                },
                {
                    "finding": "The receipt deadline changed.",
                    "quote": "Itemized receipts must be submitted within 10 calendar days after returning.",
                    "source": "Document A",
                },
                {
                    "finding": "The receipt deadline changed.",
                    "quote": "Itemized receipts must be submitted within 30 calendar days after returning.",
                    "source": "Document B",
                },
                {
                    "finding": "Airfare upgrades are excluded.",
                    "quote": "Airfare upgrades are not eligible for reimbursement.",
                    "source": "Document B",
                },
            ],
        },
    }
