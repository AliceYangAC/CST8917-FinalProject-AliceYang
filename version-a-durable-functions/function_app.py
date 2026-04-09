import azure.functions as func
import azure.durable_functions as df
import logging
from datetime import timedelta

myApp = df.DFApp(http_auth_level=func.AuthLevel.ANONYMOUS)

# client function http trigger
@myApp.route(route="expenses")
@myApp.durable_client_input(client_name="client")
async def expense_starter(req: func.HttpRequest, client: df.DurableOrchestrationClient):
    try:
        expense_data = req.get_json()
    except ValueError:
        return func.HttpResponse("Invalid JSON payload", status_code=400)

    # start orchestrator
    instance_id = await client.start_new("expense_orchestrator", client_input=expense_data)
    logging.info(f"Started orchestration with ID = '{instance_id}'.")
    
    # returns the management urls (statusCheck, sendEvent, etc)
    return client.create_check_status_response(req, instance_id)

# orchestrator function
@myApp.orchestration_trigger(context_name="context")
def expense_orchestrator(context: df.DurableOrchestrationContext):
    expense_data = context.get_input()

    # validate the input data first
    validation_result = yield context.call_activity("validate_expense", expense_data)
    if not validation_result.get("is_valid"):
        return {"status": "Validation error", "error": validation_result.get("error")}

    amount = float(expense_data.get("amount", 0))

    # check for auto-approval or human approval
    if amount < 100:
        final_status = "Auto-approved"
    else:
        # durable function pattern: human interaction w/ timeout of 10 seconds
        expiration = context.current_utc_datetime + timedelta(seconds=20)
        timeout_task = context.create_timer(expiration)
        approval_task = context.wait_for_external_event("ManagerResponse")

        # race the timer against the manager's response
        winner = yield context.task_any([approval_task, timeout_task])

        if winner == approval_task:
            final_status = approval_task.result  # approved or rejected
            timeout_task.cancel() # cancel timer if manager responds
        else:
            final_status = "Escalated" # timer completes, no manager response

    # send notification
    expense_data["final_status"] = final_status
    yield context.call_activity("send_email_notification", expense_data)

    return {"status": final_status, "expense_details": expense_data}

# activity functions
# validation activity to check for required fields, valid categories, and positive amount
@myApp.activity_trigger(input_name="expenseData")
def validate_expense(expenseData: dict):
    required_fields = ["employeeName", "employeeEmail", "amount", "category", "description", "managerEmail"]
    valid_categories = ["travel", "meals", "supplies", "equipment", "software", "other"]

    for field in required_fields:
        if field not in expenseData or not str(expenseData[field]).strip():
            return {"is_valid": False, "error": f"Missing required field: {field}"}

    if expenseData.get("category", "").lower() not in valid_categories:
        return {"is_valid": False, "error": f"Invalid category. Valid options: {', '.join(valid_categories)}"}

    try:
        if float(expenseData["amount"]) <= 0:
            return {"is_valid": False, "error": "Amount must be greater than zero."}
    except ValueError:
        return {"is_valid": False, "error": "Amount must be a numeric value."}

    return {"is_valid": True}

# mock email notification activity
@myApp.activity_trigger(input_name="expenseData")
def send_email_notification(expenseData: dict):
    logging.info(f"*** MOCK EMAIL SENT TO: {expenseData['employeeEmail']} ***")
    logging.info(f"Subject: Expense {expenseData['final_status']}")
    logging.info(f"Body: Your expense for {expenseData['category']} (${expenseData['amount']}) is {expenseData['final_status']}.")
    return "Notification sent"

# manager approval endpoint to raise external event/wake up orchestrator from timer
@myApp.route(route="expenses/{instanceId}/manager-response", methods=["POST"])
@myApp.durable_client_input(client_name="client")
async def manager_approval(req: func.HttpRequest, client: df.DurableOrchestrationClient):
    instance_id = req.route_params.get("instanceId")
    try:
        body = req.get_json()
        action = body.get("action") #  pass {"action": "Approved"} or {"action": "Rejected"}
        if action not in ["Approved", "Rejected"]:
            return func.HttpResponse("Action must be exactly 'Approved' or 'Rejected'", status_code=400)
    except ValueError:
        return func.HttpResponse("Invalid JSON payload", status_code=400)

    # raise the event to wake up sleeping orchestrator
    await client.raise_event(instance_id, "ManagerResponse", action)
    return func.HttpResponse(f"Successfully sent '{action}' response to instance {instance_id}")