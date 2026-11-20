# Interview and public-release notes

## Tell the story in three moves

- **Business rule:** If two people request the final item, only one reservation may succeed. Show the low-stock lamp, place one order, then request too many. Point to the unchanged inventory after the rejection.
- **Engineering decision:** Persist the order, its reservation and its first event together. The browser can refresh or lose a response without turning partially written records into the source of truth. Do not claim that order creation itself is retry-safe: guaranteeing that would need an idempotency key.
- **Trade-off:** SQLite makes an offline walkthrough repeatable. The fulfillment simulator removes carrier credentials and timing guesses. For a hosted multi-user service, revisit authentication, write throughput, retry handling, and delivery of external events. Those are design discussion points, not delivered features.

## Optional AI interview example

Ask how many lamps are available before and after reserving one. Compare the selected model’s answer with the inventory register, and explain why the database, not the model, owns that number. OpenAI and Anthropic are alternatives, not two calls per question. Don’t display credentials on screen. Verify your right to use the assistant’s display name before publishing; rename it if it is company branding.

## Sample résumé bullet

Built a local-first inventory and fulfillment demo in React, FastAPI, and SQLite; implemented transactional reservations to prevent overselling and added a read-only AI assistant that can explain synthetic stock and order data through OpenAI or Anthropic.

## Before the first public GitHub push

1. Use a new, empty GitHub repository. Import only the extracted source bundle. Do not reuse a work repository, fork, remote, or history.
2. Read the source, lockfile, docs and any added screenshots. Keep only synthetic examples. Exclude databases, dependency trees, build output, logs, environment files and personal paths. Use only demo screenshots captured with a clean browser profile and no personal chrome visible.
3. Review `git status --short`, `git diff --cached`, your public commit author name/email, and `git remote -v` in the new project. Consider your GitHub noreply address. Check repository visibility and destination before pushing.
4. Decide what license you intend to grant and confirm that you have the right to publish the material. This demo ships without an open-source license selection. No scanner or substitution of names can grant publication rights.
5. The demo is designed to run locally; publishing source does **not** mean deploying the server publicly. Do not put a locally configured order API on the internet as-is.
