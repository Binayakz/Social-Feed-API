# Design Decisions

## 1. FastAPI as the API Framework

FastAPI was chosen for:

- strong request/response validation
- async support
- automatic OpenAPI docs
- a small amount of framework overhead for a take-home backend

It fits well for an API-first project where speed of implementation still needs good structure.

## 2. PostgreSQL as the Primary Database

PostgreSQL was chosen because the domain is strongly relational:

- users
- posts
- comments
- likes
- visibility rules

Why it fits:

- mature indexing support
- transactional consistency
- good SQL ergonomics for aggregate queries

## 3. SQLAlchemy 2.0 Async ORM

SQLAlchemy async keeps the data layer aligned with FastAPI’s async request model while still allowing more explicit SQL when needed.

Why this mattered:

- easy ORM modeling early on
- compatible with Alembic
- flexible enough to move from simple relationship loading to optimized SQL aggregation later

## 4. Alembic for Schema Migrations

Schema changes are tracked with Alembic rather than manual edits.

Why:

- repeatable local and EC2 deployments
- explicit migration history
- safer promotion across environments

## 5. UUID Primary Keys

UUIDs are used for major entities.

Why:

- less predictable public identifiers
- easier to expose in APIs
- works well if the system ever grows beyond a single-node mental model

Tradeoff:

- larger indexes than integer keys

## 6. JWT-Based Authentication

The project uses stateless JWT bearer auth.

Why:

- simple frontend integration
- no session table required
- straightforward deployment in a single API service

Current tradeoff:

- no refresh-token/session rotation yet

## 7. HTTP Bearer for Protected Routes

Protected endpoints use bearer tokens via `HTTPBearer`.

Why:

- the project uses a custom JSON login flow
- this matches the real client integration better than pretending to use OAuth password flow
- Swagger testing stays straightforward

## 8. Explicit Public/Private Post Visibility

Posts use an enum:

- `public`
- `private`

Why:

- maps directly to the assignment requirement
- keeps visibility rules explicit in both storage and query logic

Visibility is enforced in service-layer queries, not delegated to the frontend.

## 9. Replies Stored in the Comments Table

Replies use `comments.parent_id` instead of a separate replies table.

Why:

- simpler schema
- reuse of comment-like logic
- one set of models and constraints

Tradeoff:

- reply depth must be limited in application logic

## 10. One-Level Reply Limit

Only one reply level is supported.

Why:

- it matches the stated product need
- keeps read and write logic manageable
- avoids recursive tree complexity in a take-home scope

## 11. Separate Like Tables for Posts and Comments

Two tables are used:

- `post_likes`
- `comment_likes`

Why:

- simple uniqueness constraints
- easy query composition
- avoids polymorphic association complexity

Replies are covered automatically because replies are stored as comments.

## 12. Feed State Is Returned Directly

Post and comment responses include frontend-ready state such as:

- `like_count`
- `comment_count`
- `liked_by_me`
- `likers_preview`

Why:

- lowers frontend complexity
- reduces follow-up API calls
- makes feed rendering direct and predictable

## 13. DB-Side Aggregation for Feed and Comment State

Counts and liked-state are computed in SQL rather than only by relationship loading.

Why:

- better scaling behavior
- avoids loading large like collections just to compute booleans/counts
- fits feed-style read patterns much better

This was an intentional evolution from the simpler first-pass approach.

## 14. Cursor Pagination for Posts and Comments

Posts and comments use cursor/keyset pagination based on `(created_at, id)`.

Why:

- scales better than offset for large feeds
- gives stable ordering across pages
- matches the “many posts and reads” requirement more credibly

Tradeoff:

- response shape becomes page-based instead of plain arrays

## 15. Indexes Matched to Feed Access Patterns

The schema includes indexes aligned with:

- author feed scans
- public feed scans
- post comment scans
- reply lookups

Why:

- query shape changes are not enough without matching indexes
- feed and comment pagination benefit directly from these access-path indexes

## 16. Separate Upload Endpoint for Post Images

The system keeps `POST /uploads/post-image` as a dedicated upload endpoint.

Why:

- isolates storage concerns
- useful for clients that prefer upload-first flows
- keeps the original JSON post endpoint simple

## 17. Additional Multipart Compose Endpoint

A second post-creation path was added:

- `POST /posts/compose`

Why:

- simplifies clients that want one request for image + post creation
- allows either text-only, image-only, or text+image posts
- keeps the original `POST /posts` endpoint unchanged for compatibility

Tradeoff:

- because `posts.content` remains non-null, image-only posts currently store an empty string for content

## 18. S3 for Media Storage

Post images and profile images are stored in S3.

Why:

- durable storage outside the container
- works across restarts and redeploys
- easy public URL generation for frontend rendering

## 19. Restricted Public Prefix Strategy

The current design allows public reads only for selected object prefixes such as:

- `post-images/*`
- `profile-images/*`

Why:

- very simple for assignment delivery
- avoids opening the whole bucket

Tradeoff:

- stricter production setups might prefer CloudFront or presigned GET URLs

## 20. Hardened Image Upload Validation

Upload validation checks:

- max size
- declared content type
- magic bytes / file signature
- real image decode through Pillow
- max pixel count

Why:

- client-provided MIME type alone is not trustworthy
- images are a common abuse surface
- this is a strong security improvement with limited implementation cost

## 21. Optional Profile Images on Users

Users have optional `profile_image_url`.

Why:

- better frontend UX than initials-only avatars
- still keeps initials as the fallback
- stays small enough for the current scope

Tradeoff:

- replacing an avatar does not currently delete the old file from S3

## 22. Redis / Valkey for Rate Limiting

Rate limiting uses Redis-compatible storage rather than Postgres.

Why:

- simple atomic counters
- avoids polluting relational storage with short-lived rate-limit data
- appropriate for auth and write-path protection

Protected areas include:

- login
- register
- post creation
- comment creation
- likes
- uploads

## 23. Deployment Uses Commit-SHA Images

The deployment flow builds both:

- commit-SHA tag
- `latest`

but EC2 is expected to run the commit-SHA image.

Why:

- avoids ambiguity about what code is running
- makes debugging bad deploys much easier

The workflow now verifies the running image and waits for `/health`.

## 24. Post-Deploy Cleanup on EC2

Deployment cleanup prunes:

- stopped containers
- unused images
- build cache
- unused volumes
- old logs and package caches

Why:

- small EC2 root volumes fill up quickly with repeated Docker deploys
- this keeps deployment reliability higher over time

## 25. Current Tradeoffs

The project intentionally prioritizes:

- correctness
- clarity
- strong assignment coverage
- pragmatic production-minded improvements

Still left intentionally simple:

- no refresh-token architecture yet
- no direct-to-S3 browser uploads yet
- no avatar/file deletion lifecycle
- no broad automated test suite yet
