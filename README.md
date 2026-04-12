# Final Project: Compare & Contrast — Dual Implementation of an Expense Approval Workflow

- **Name:** Alice Yang
- **Student Number:** 041200019
- **Course Code:** CST8917: Serverless Applications
- **Project Title:** Dual Implementation of an Expense Approval Workflow
- **Date:** 04/09/2026

---

## Version A Summary (Durable Functions)
- **Description:** Version A implements the workflow entirely in code using Azure Durable Functions (Python 3.12). It utilizes an HTTP Trigger client function to trigger an Orchestrator function, which manages the state and calls subsequent Activity functions for validation and processing.
- **Design Decisions:** To ensure API tests accurately received `400 Bad Request` errors for missing fields, I implemented synchronous validation inside the HTTP Starter function before calling `StartNewAsync`. This intercepted problematic payloads before it was queued, avoiding silent background failures.
- **Challenges:** Implementing the Human Interaction pattern required using Durable Timers, the `WaitForExternalEvent` and a `CreateTimer` tasks. Managing this state and building the custom HTTP endpoints required to pass the manager's "Approve" or "Reject" payloads back to the specific orchestration instance was a higher hurdle compared to a visual approach in Logic Apps in Version B.

## Version B Summary (Logic Apps, Service Bus)
- **Description:** Version B is a decoupled, event-driven architecture. A Service Bus Queue ingests requests, triggering a Logic App orchestrator. The Logic App passes data to a single Python Azure Function for just validation, then routes the results to a Service Bus Topic with filtered subscriptions (`approved-sub`, `rejected-sub`, `escalated-sub`, `failed-sub`).
- **Manager Approval Approach:** I utilized the Outlook "Send email with options" connector. This natively pauses the Logic App and sends an actionable HTML email to the manager. For the timeout (Scenario 4), I adjusted the action's timeout settings (e.g., `PT20S`) and added a parallel escalation branch configured to `Run after -> has timed out`.
- **Challenges:** E2E local testing was the biggest challenge. Because the Service Bus REST API requires Shared Access Signatures (SAS), I could not simply use a basic `.http` file. I had to generate a SAS token to authenticate my VS Code REST Client requests against the Azure resources.

---

## Comparison Analysis

### 1. Development Experience
Version A (Durable Functions) takes a code-first approach written in Python, thus providing a high degree of control over the logic flow, data structures, and state management. The learning curve primarily involved understanding the orchestrator's constraints, like the need for deterministic code. [1] I want to emphasize too that the ability to debug and step through orchestrator and activity code mid-execution through the terminal in VSCode allowed me a high degree of confidence that the logic was behaving correctly before any cloud deployment.

Version B (Logic Apps and Service Bus) shifted instead to a more visual & design-focused model. Architecting the workflow became much more "tactile," moving heavily away from code except for the validation logic still conducted by the Function. However, Version B required significantly more Azure infra setup. Provisioning the Service Bus, queues, topics, and filtered subscriptions was necessary before the orchestration could even be built. While Version A felt like traditional development where the logic is all built and verified in code, Version B felt like putting building blocks together whose branches could only be tested when all the required Azure resources were fully deployed, linked up, and saved.

### 2. Testability
My last few points lead to my verdict here. Version A offered a much superior local testing experience. The VSCode REST Client and `.http` files allowed me to spin up the entire orchestration process locally alongside using the Azure Functions Core Tools and Azurite. Then, it was simple to mock payloads, trigger the HTTP client function, and debug Python code to verify logic.

Version B was comparatively quite a bit harder to test E2E locally. While the standalone Python validation function could be tested in isolation using `.http` files, triggering the actual Logic App required pushing messages to the live and configured Azure Service Bus with its queue and topics fully setup. Furthermore, since the Service Bus REST API uses SAS tokens, testing required either running a custom script to generate a token [2] for the `.http` file (as I show in the demo), or manually pasting JSON payloads into the Service Bus Explorer in the Azure Portal. In conclusion, local testing is direct for Version A, but very limited for E2E Version B.

### 3. Error Handling
Error handling in Durable Functions (Version A) is just as straightforward as testing from my experience through using VSCode terminal and debug mode as needed, and `try/except` blocks. For example, Durable Functions offers robust, built-in `RetryOptions` for activity calls, with full support for custom retry counts, intervals, and exponential backoff [3], all expressed directly in code.

In Logic Apps (Version B), error handling relies on the "Configure run after" setting on actions. [4] Catching validation errors from the Python function required parsing the JSON response and using a Switch/Condition control to route the `"validation-error"` status to a dedicated Service Bus branch (publishing to a `failed-sub` subscription). Handling the manager timeout required configuring a parallel branch to execute explicitly when the email action timed out. While visually simple to understand, error handling in Version B can quickly feel cumbersome compared to how Version A handles it just with  `try/except` blocks.

### 4. Human Interaction Pattern
The requirement to wait for a manager's approval highlighted the fundamental difference between the two architectures. In Version A, the orchestrator utilized `WaitForExternalEvent` alongside a durable timer (`CreateTimer`). This put the orchestrator to sleep, completely freeing up compute resources, but it required building custom HTTP endpoints to manually route the manager's "Approve" or "Reject" payloads back to the specific instance ID.

Version B handled this requirement far more naturally. Logic Apps lacks a direct `WaitForExternalEvent` method, but it natively supports business approval workflows via the "Send email with options" connector. This action automatically paused the workflow and generated an actionable HTML email. The manager simply clicked a button in their inbox to resume the workflow. Setting the timeout (e.g., `PT1M`) was done directly in the action's settings, making the Human Interaction pattern in Version B much more suited to end-users, requiring zero custom UI or routing logic.

### 5. Observability
Monitoring runs and diagnosing problems was easier Version B due to the native UI of the Logic Apps designer. In particular, the "Runs history" provided a highly visual, step-by-step graphical view of every execution. By clicking on any step, it was clear what inputs were passed to the Python function and what outputs were received, making it easy to identify exactly which conditional branch was taken and why. In addition, the highly visual cues by color and shape made it obvious which action caused failures, or which branches were taken in a run.

Version A's observability relied on the `statusQueryGetUri` provided by the initial 202 response. Checking the status required polling the instance status endpoint to inspect `runtimeStatus` and `output`. Diagnosing a failure in practice meant either querying `traces` and `exceptions` tables in Log Analytics via Application Insights or parsing long lists of events in Application Insights logs, which is a much more tedious process than clicking a red step in a Logic Apps run history.

### 6. Costs

#### Assumptions

##### Workflow Logic 
1. Trigger: Receive request (HTTP for Durable / Service Bus for Logic Apps).
2. Validation: One execution of the Python validation logic.
3. Condition: Check if amount is ≥$100.
4. Wait/Approval: System waits for manager or timer (15 min).

##### Version A
1. Execution Count: Each expense run triggers 5 internal executions (1x Client, 1x Orchestrator logic, 1x Validation activity, 1x Notification activity, and 1x Durable Timer/Manager logic).
2. Performance: Assumes 128 MB memory allocation and a 200ms average duration per execution.
##### Version B
1. Workflow Steps: Each Logic App run executes 10 Actions (triggers, variable initialization, conditionals, and control steps).
2. External Calls: Each run uses 4 Standard Connectors (Service Bus Trigger, Azure Function Call, Service Bus Topic Send, and Office 365/Email).
3. Messaging: Service Bus requires the Standard Tier to support the Topics and Subscriptions defined in the Terraform. Each expense involves 3 Operations (Queue push, Topic push, and Subscription pull).
4. Outcome: Send one notification email and log to storage.

#### Monthly Cost Comparison
*Note: All prices are based on the estimates provided in the XLSX files in `/presentation/price_calculator`, expored from Azure Pricing Calculator [5]*

| Version                          | 100 Expenses/Day | 10,000 Expenses/Day |
| :------------------------------- | :--------------- | :------------------ |
| **Version A: Durable Functions** | **$0.70**        | **$9.25**           |
| **Version B: Logic Apps**        | **$12.64**       | **$243.76**         |

#### Cost Breakdown Summary

**Version A: Durable Functions**

* **100/day:** The cost is almost entirely dominated by the **Storage Account** ($0.70). The Azure Functions compute cost is $0.00 because it stays well within the monthly free grant (1 million executions).
* **10,000/day:** As volume increases to 1.5 million executions per month, you begin to exceed the free grant slightly, but the primary cost driver remains **Storage Transactions** and capacity ($9.05) due to the high-write nature of Durable Functions state management.

**Version B: Logic Apps**

* **100/day:** The cost is significantly higher even at low volume due to the **Service Bus Standard Tier base charge** (approx. $9.81). Logic App actions add another ~$2.15.
* **10,000/day:** Logic Apps become the dominant cost factor ($224.90). Because Logic Apps are billed per action and per connector execution, the high volume of 100,000 actions and 40,000 connectors per day scales the price linearly and rapidly compared to the Functions model.

### 7. Recommendation

I would recommend **Version B (Logic Apps, Service Bus)**.

While Version A provides a better local development and testing environment, Version B much more intuitively provided the tools to build a human interaction process. The native "Send email with options" Outlook connector eliminates the need to build a custom frontend or complex routing logic for manager approvals. Furthermore, the Service Bus architecture with filtered subscriptions (`approved-sub`, `rejected-sub`, `escalated-sub`, `failed-sub`) creates a decoupled, event-driven system from default. For example, in this hypothetical, if the finance department later decides they want to ingest all approved expenses into an external data sink, they simply attach a new consumer to the `approved-sub` subscription without modifying the Logic App at all. This would not be the case for just Durable Functions.

I would say that **Version A (Durable Functions)** is best for workflows that require complex, highly customized logic requirements, heavy compute, or "Fan-out/Fan-in" processing patterns, which Functions excel at most. For example, the PDF batch processing pipeline that spawns parallel activity workers per document that we explored for the midterm. These are scenarios that become cumbersome to represent visually with the many branches required. 


---

## References (IEEE)

[1] Microsoft, "Durable Functions code constraints," Azure Functions Documentation, Microsoft Learn. [Online]. Available: https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-code-constraints

[2] Microsoft, "Service Bus authentication and authorization with Shared Access Signatures," Azure Service Bus Documentation, Microsoft Learn. [Online]. Available: https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-sas

[3] Microsoft, "Handle errors in Durable Functions," Azure Functions Documentation, Microsoft Learn. [Online]. Available: https://learn.microsoft.com/en-us/azure/azure-functions/durable/durable-functions-error-handling

[4] Microsoft, "Handle and throw errors or exceptions in Azure Logic Apps," Azure Logic Apps Documentation, Microsoft Learn. [Online]. Available: https://learn.microsoft.com/en-us/azure/logic-apps/logic-apps-exception-handling

[5] Microsoft, "Azure Pricing Calculator," Microsoft Azure. [Online]. Available: https://azure.microsoft.com/pricing/calculator/

---

## AI Disclosure
I utilized AI to help me troubleshoot Azure Service Bus SAS token generation when I ran into auth issues, and explain the asynchronous "Human Interaction" pattern for Durable Functions to help me implement Durable Timers. I also used it to help format this README.