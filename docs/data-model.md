# Data model

Project requirement 2: design the data model. Requirement 3: store it in a NoSQL
data store. We use **Firestore** (Google Cloud's managed document database): data
is stored as JSON-like documents grouped in collections, with no fixed schema
(Data Models lecture, slide 9). Locally and in tests, the same interface is
implemented by an in-memory dictionary.

## Collections

| Path | One document = | Fields | Written by | Read by |
| --- | --- | --- | --- | --- |
| `products/{productId}` | a product | `name` (string), `category` (string, lower case), `price` (number ≥ 0), `description` (string), `popularity` (integer ≥ 0) | catalog-service (POST/PATCH/DELETE, seed script) | catalog-service; recommendations via the catalog API |
| `users/{userId}/events/{eventId}` | one action of a user | `productId` (string), `type` (`view`, `cart`, `purchase`), `timestamp` (ISO 8601 UTC string), `userId` | catalog-service (POST events) | catalog-service; v1 rules and v2 tools via the catalog API |

Recommendation logs (`event="recommendation"`, one per request) are not stored in
Firestore: they are JSON lines written to stdout, which Cloud Run sends to
**Cloud Logging**. They feed the dashboard and the cost report.

| Log field | Meaning |
| --- | --- |
| `version` | `v1` or `v2` |
| `source` | `rules` (v1), `agent` (v2's own answer), `fallback` (v2 failed, rules answered), `none` (error) |
| `valid` | the answer passed the validator AND came from the intended decision-maker |
| `reason` | why v2 fell back, or which rule failed |
| `latency_ms` | time spent in the service |
| `tool_calls`, `turns` | which tools the model chose, and how many model calls it took |
| `input_tokens`, `output_tokens`, `cost_usd` | model usage and its cost for this request |

## Design choices

- **Events as a sub-collection of each user.** "This user's latest 50 events,
  newest first" is the only query we need; inside one user's sub-collection it
  is a single-field `order_by(timestamp)`, which Firestore indexes automatically.
- **Product ids are stable strings** (`p001`...). The seed keeps them, so tests,
  demos and the report can refer to the same products.
- **The API representation is not the database.** Responses add `href` and
  hide storage details (REST lecture, slide 7).
- **Shared state lives in Firestore, never in a process.** Several gunicorn
  workers and Cloud Run instances must see the same data (REST lecture, slide 20);
  we hit exactly that bug locally with two workers and in-memory storage.
