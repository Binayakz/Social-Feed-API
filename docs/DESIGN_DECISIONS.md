# Design Decisions

## 1. FastAPI as the API Framework

FastAPI was chosen because it provides:
- strong request/response validation through Pydantic
- clean async support
- automatic OpenAPI documentation
- fast iteration speed for backend API development

This makes it a strong fit for a take-home backend project where correctness and clarity matter.

## 2. PostgreSQL as the Primary Database

PostgreSQL was selected because it is a mature relational database with:
- strong transactional guarantees
- good indexing support
- excellent fit for relational social-feed data
- wide production use

The data model for users, posts, comments, and likes is naturally relational, so PostgreSQL is a better fit than a document store for this design.

## 3. SQLAlchemy 2.0 Async ORM

SQLAlchemy async support was used to keep the stack aligned with FastAPI’s async request handling.

Reasons:
- good ecosystem maturity
- clear ORM modeling
- compatibility with Alembic
- flexible query control when moving from simple ORM loading to more optimized SQL later

## 4. Alembic for Schema Migrations

Schema changes are managed through Alembic rather than manual database edits.

Reasons:
- repeatable deployments
- explicit schema history
- safer promotion across local and deployed environments

## 5. UUID Primary Keys

UUIDs are used for major entities instead of integer IDs.

Reasons:
- less predictable identifiers
- easier merging/distribution if system scale grows
- cleaner external exposure in APIs

Tradeoff:
- larger indexes than integers

For this project, the benefits outweigh the cost.

## 6. JWT-Based Authentication

The system uses stateless JWT authentication instead of server-side sessions.

Reasons:
- simple frontend integration
- easy protection of API routes
- no session store required
- straightforward deploy model for a single API service

## 7. HTTP Bearer Auth Instead of OAuth Password Flow in Swagger

Protected routes use bearer token auth through `HTTPBearer`.

Reason:
- the backend uses a custom JSON login flow, not a full OAuth2 password token exchange
- `HTTPBearer` matches the real client usage better
- Swagger becomes simpler for manual testing

## 8. Public/Private Post Visibility

Posts are modeled with an explicit visibility enum:
- `public`
- `private`

Reason:
- this keeps authorization rules explicit in the database and service layer
- supports the assignment requirement directly

Visibility is enforced in service queries, not left to frontend behavior.

## 9. Replies Stored in the Comments Table

Replies are stored in the same `comments` table via `parent_id`.

Reasons:
- simpler schema
- no separate replies table needed
- same rules and like system can be reused

Tradeoff:
- nested reply depth must be enforced by logic

## 10. One-Level Reply Limit

The system allows one level of replies only.

Reason:
- matches the assignment need without introducing recursive tree complexity
- keeps query and response logic simpler

This is a deliberate simplification, not an accidental limitation.

## 11. Separate Like Tables for Posts and Comments

Two like tables are used:
- `post_likes`
- `comment_likes`

Reasons:
- simple uniqueness constraints
- straightforward queries
- avoids polymorphic-like-table complexity

Replies are covered automatically because replies are stored as comments.

## 12. Separate Upload Endpoint

Image upload is handled separately from post creation.

Flow:
1. upload file
2. receive URL
3. create post with `image_url`

Reasons:
- keeps post creation API simple
- isolates storage concerns
- frontend can manage upload progress separately

## 13. S3 for Image Storage

Uploaded images are stored in S3 instead of local disk.

Reasons:
- better deployment portability
- works naturally across containers and EC2 restarts
- supports future CDN/public serving options

## 14. Public Image Prefix Strategy

The current design uses a restricted public-read prefix for uploaded post images.

Reason:
- simplest way to make uploaded images frontend-renderable for this assignment
- avoids more complex private-media delivery setup

Tradeoff:
- for stricter production use, CloudFront or presigned GET URLs would be preferable

## 15. Offset Pagination for the Feed

The feed currently uses offset/limit pagination.

Reason:
- simpler to implement and explain
- enough for assignment/demo usage

Tradeoff:
- not ideal at very high scale

Future improvement:
- cursor/keyset pagination using `(created_at, id)`

## 16. Response-Level Feed State

The API returns:
- `like_count`
- `comment_count`
- `liked_by_me`

Reason:
- this makes the frontend much easier to build
- reduces follow-up calls for common feed rendering

Current tradeoff:
- some of this state is still derived in application logic and can be pushed down into optimized SQL later

## 17. Migration-on-Startup in Docker

The Docker startup command runs:
- `alembic upgrade head`
- then starts the app

Reason:
- keeps deployed schema aligned with code automatically
- reduces manual deployment steps

Tradeoff:
- production teams sometimes prefer a separate migration step

For this project, the simpler deploy path is worth it.

## 18. Current Known Tradeoffs

The project intentionally prioritizes:
- correctness
- feature completeness
- clarity

over advanced production optimizations.

Known areas for future improvement:
- DB-side feed aggregation
- cursor pagination
- rate limiting
- stronger upload content validation
- broader tests
