# Comparison Analysis

## 1. Development Experience
Version A (Durable Functions) takes a code-first approach written in Python, thus providing a high degree of control over the logic flow, data structures, and state management. The learning curve primarily involved understanding the orchestrator's constraints, like the need for deterministic code. I want to emphasize too that the ability to debug and step through orchestrator and activity code mid-execution through the terminal in VSCode allowed me a high degree of confidence that the logic was behaving correctly before any cloud deployment.

Version B (Logic Apps and Service Bus) shifted instead to a more visual & design-focused model. Architecting the workflow became much more "tactile," moving heavily away from code except for the validation logic still conducted by the Function. However, Version B required significantly more Azure infra setup. Provisioning the Service Bus, queues, topics, and filtered subscriptions was necessary before the orchestration could even be built. While Version A felt like traditional development where the logic is all built and verified in code, Version B felt like putting building blocks together whose branches could only be tested when all the required Azure resources were fully deployed, linked up, and saved.

## 2. Testability
My last few points lead to my verdict here. Version A offered a much superior local testing experience. The VSCode REST Client and `.http` files allowed me to spin up the entire orchestration process locally alongside using the Azure Functions Core Tools and Azurite. Then, it was simple to mock payloads, trigger the HTTP client function, and debug Python code to verify logic.

Version B was comparatively quite a bit harder to test E2E locally. While the standalone Python validation function could be tested in isolation using `.http` files, triggering the actual Logic App required pushing messages to the live and configured Azure Service Bus with its queue and topics fully setup. Furthermore, since the Service Bus REST API uses SAS tokens, testing required either running a custom script to generate a token for the `.http` file (as I show in the demo), or manually pasting JSON payloads into the Service Bus Explorer in the Azure Portal. In conclusion, local testing is direct for Version A, but very limited for E2E Version B.

## 3. Error Handling
Error handling in Durable Functions (Version A) is just as straightforward as testing from my experience through using VSCode terminal and debug mode as needed, and `try/except` blocks. For example, Durable Functions offers robust, built-in `RetryOptions` for activity calls, with full support for custom retry counts, intervals, and exponential backoff, all expressed directly in code.

In Logic Apps (Version B), error handling relies on the "Configure run after" setting on actions. Catching validation errors from the Python function required parsing the JSON response and using a Switch/Condition control to route the `"validation-error"` status to a dedicated Service Bus branch (publishing to a `failed-sub` subscription). Handling the manager timeout required configuring a parallel branch to execute explicitly when the email action timed out. While visually simple to understand, error handling in Version B can quickly feel cumbersome compared to how Version A handles it just with  `try/except` blocks.

## 4. Human Interaction Pattern
The requirement to wait for a manager's approval highlighted the fundamental difference between the two architectures. In Version A, the orchestrator utilized `WaitForExternalEvent` alongside a durable timer (`CreateTimer`). This put the orchestrator to sleep, completely freeing up compute resources, but it required building custom HTTP endpoints to manually route the manager's "Approve" or "Reject" payloads back to the specific instance ID.

Version B handled this requirement far more naturally. Logic Apps lacks a direct `WaitForExternalEvent` method, but it natively supports business approval workflows via the "Send email with options" connector. This action automatically paused the workflow and generated an actionable HTML email. The manager simply clicked a button in their inbox to resume the workflow. Setting the timeout (e.g., `PT1M`) was done directly in the action's settings, making the Human Interaction pattern in Version B much more suited to end-users, requiring zero custom UI or routing logic.

## 5. Observability
Monitoring runs and diagnosing problems was easier Version B due to the native UI of the Logic Apps designer. In particular, the "Runs history" provided a highly visual, step-by-step graphical view of every execution. By clicking on any step, it was clear what inputs were passed to the Python function and what outputs were received, making it easy to identify exactly which conditional branch was taken and why. In addition, the highly visual cues by color and shape made it obvious which action caused failures, or which branches were taken in a run.

Version A's observability relied on the `statusQueryGetUri` provided by the initial 202 response. Checking the status required polling the instance status endpoint to inspect `runtimeStatus` and `output`. Diagnosing a failure in practice meant either querying `traces` and `exceptions` tables in Log Analytics via Application Insights or parsing long lists of events in Application Insights logs, which is a much more tedious process than clicking a red step in a Logic Apps run history.

## Costs

[Estimate cost at ~100 expenses/day and ~10,000 expenses/day. Use the Azure Pricing Calculator and state your assumptions.]

## Recommendation

I would recommend **Version B (Logic Apps, Service Bus)**.

While Version A provides a better local development and testing environment, Version B excels where this type of business process matters most in human interaction and service integration. The native "Send email with options" Outlook connector eliminates the need to build a custom frontend or complex routing logic for manager approvals. Furthermore, the Service Bus architecture with filtered subscriptions (`approved-sub`, `rejected-sub`, `escalated-sub`, `failed-sub`) creates a decoupled, event-driven system from default. For example, in this hypothetical, if the finance department later decides they want to ingest all approved expenses into an external data sink, they simply attach a new consumer to the `approved-sub` subscription without modifying the Logic App at all. This would not be the case for just Durable Functions.

I would say that **Version A (Durable Functions)** is best for workflows that require complex, highly customized logic requirements, heavy compute, or "Fan-out/Fan-in" processing patterns, which Functions excel at most. For example, the PDF batch processing pipeline that spawns parallel activity workers per document that we explored for the midterm. These are scenarios that become cumbersome to represent visually with the many branches required. 
