# Production Preparation Process Automation

This module automates the entire production order preparation workflow in Odoo using XML-RPC communication. It is responsible for fetching orders, analyzing client relationships, creating directory structures on the server, updating sale order lines, and finalizing production operations.

It serves as an integration layer between Odoo and the file system environment, eliminating manual tasks previously performed by production staff and ensuring data consistency between the system and the document structure.


## Key Program Assumptions:

- Communication with Odoo is handled via XML-RPC (`common` and `object` modules).
- The program runs interactively in the terminal via command-line inputs.
- Only orders meeting the following criteria are processed:
  - In `confirmed` state (manufacturing orders),
  - Work order "Przygotowanie produkcji" (Production Preparation) in `ready` state.
- The program creates folders in the following path:
  - `/PRODUKCJA/ZAMOWIENIA PRODUKCJI/`
- Directory structures are copied from:
  - `--- NARZEDZIA ---/<service_name>/.../directory_structure/`
- The client is identified based on the partner assigned to the work order.
- Handles linked orders (e.g., annual tax settlements).
- Completes the work order and posts a message to the chatter generated from a template.


## Main Module Components:

1. `get_all_productions()`
   - Fetches all active manufacturing orders in `confirmed` state, excluding products from the Helpdesk and TD departments.
   - Filters out orders containing the "Odroczenie" (Postponement) activity.
   - Returns a list of dictionaries containing core production data.

2. `get_preparation_workorders()`
   - Fetches work orders named "Przygotowanie produkcji" in `ready` state.
   - Links them with their corresponding MRP manufacturing orders.
   - Returns a list of unified records ready for further processing.

3. `find_linked_orders()`
   - Analyzes relationships between clients (e.g., spouse, fiscal partner) and checks for other orders sharing the same `origin`.
   - Primary use case: "Annual Tax Settlement" services.
   - Returns a list of linked WHMO numbers.

4. `copy_structure()`
   - Locates the appropriate directory structure template for a given service.
   - Copies the structure to the newly created order folder.
   - Automatically replaces the "Imię Nazwisko" (First Name Last Name) placeholder folder with the client's actual name.
   - Ensures consistency across production documentation.

5. `append_whmo_to_sale_line()`
   - Appends the WHMO number to the corresponding Sale Order (SO) line if the production product matches the line item product.
   - Prevents duplicate entries.
   - Returns a boolean status indicating whether the operation succeeded.

6. `finish_preparation_workorder()`
   - Verifies the folder preparation accuracy (existence of structure, WHMO reference added).
   - Automatically completes the "Przygotowanie produkcji" work order operation (`button_finish`).
   - Returns the execution success status.

7. `post_message_from_template()`
   - Posts a message to the manufacturing order chatter based on an email template.
   - Used for automated notification upon production launch.
   - Returns `True`/`False` based on execution success.

8. `get_client_name()`
   - Resolves the correct client name based on the work order partner.
   - Returns a formatted name string ready for use in directory structures.
