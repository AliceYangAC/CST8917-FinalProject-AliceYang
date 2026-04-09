import azure.functions as func
import json
import logging

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.function_name(name="validate-expense")
@app.route(route="", methods=["POST"])
def validate_expense(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("Validating expense request from Logic App.")

    try:
        expense_data = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"status": "validation-error", "error": "Invalid JSON payload"}),
            mimetype="application/json",
            status_code=400
        )

    required_fields = ["employeeName", "employeeEmail", "amount", "category", "description", "managerEmail"]
    valid_categories = ["travel", "meals", "supplies", "equipment", "software", "other"]

    # validate required fields
    missing = [field for field in required_fields if field not in expense_data or not str(expense_data[field]).strip()]
    if missing:
        return func.HttpResponse(
            json.dumps({"status": "validation-error", "error": f"Missing required fields: {', '.join(missing)}"}),
            mimetype="application/json",
            status_code=400
        )

    # validate category
    if expense_data.get("category", "").lower() not in valid_categories:
        return func.HttpResponse(
            json.dumps({"status": "validation-error", "error": f"Invalid category. Must be one of: {', '.join(valid_categories)}"}),
            mimetype="application/json",
            status_code=400
        )

    # validate amount
    try:
        amount = float(expense_data["amount"])
        if amount <= 0:
            return func.HttpResponse(
                json.dumps({"status": "validation-error", "error": "Amount must be greater than zero."}),
                mimetype="application/json",
                status_code=400
            )
    except ValueError:
        return func.HttpResponse(
            json.dumps({"status": "validation-error", "error": "Amount must be a numeric value."}),
            mimetype="application/json",
            status_code=400
        )

    # validate business logic
    if amount < 100:
        workflow_status = "auto-approved"
    else:
        workflow_status = "requires-manager"

    # return 200 OK w the routing status and original data for the Logic App to use
    response_payload = {
        "status": workflow_status,
        "employeeName": expense_data["employeeName"],
        "employeeEmail": expense_data["employeeEmail"],
        "managerEmail": expense_data["managerEmail"],
        "amount": amount,
        "description": expense_data["description"]
    }

    return func.HttpResponse(
        json.dumps(response_payload),
        mimetype="application/json",
        status_code=200
    )