# Architecture

## Overview

This project is a layered FastAPI backend for a social feed product. The system is organized so HTTP concerns, business rules, persistence, and infrastructure stay separated. That keeps route handlers thin and makes it easier to evolve features like pagination, upload validation, and authorization without tangling the whole codebase.

The current backend supports:

- JWT auth
- protected feed access
- public/private posts
- comments and one-level replies
- like/unlike flows
- cursor pagination for posts and comments
- DB-side aggregation for feed and comment state
- S3-backed post and profile image uploads
- Redis-backed rate limiting

## High-Level Layers

The application follows a service-oriented layered structure:

1. API layer
2. service layer
3. persistence layer
4. schema layer
5. infrastructure layer

## API Layer

Location:

- `app/api/routes`
- `app/api/router.py`
- `app/api/deps.py`

Responsibilities:

- define HTTP endpoints
- parse request bodies, query params, forms, and file uploads
- attach auth and rate-limit dependencies
- convert domain errors into HTTP responses
- return response schemas

Current route groups:

- `auth.py`
- `post.py`
- `comment.py`
- `like.py`
- `upload.py`
- `user.py`

Examples of thin-controller behavior:

- `POST /posts/compose` uploads an optional file, then delegates post creation to the service layer
- `POST /users/me/profile-image` uploads the avatar, then delegates user update to the service layer

## Service Layer

Location:

- `app/services`

Responsibilities:

- business rules
- visibility enforcement
- feed and comment query composition
- upload orchestration
- liker preview shaping
- user profile updates

Important services:

- `user_service.py`
- `post_service.py`
- `comment_service.py`
- `like_service.py`
- `storage_service.py`

Design pattern:

- query-heavy services build explicit SQLAlchemy statements
- serialization happens in service helpers before API responses are returned
- routes do not directly manipulate ORM state beyond calling services

## Persistence Layer

Location:

- `app/models`
- `app/db`
- `alembic`

Responsibilities:

- relational modeling
- async session handling
- migration history
- indexes for feed/comment access patterns

Storage choices:

- PostgreSQL for relational data
- UUID primary keys
- Alembic for schema migrations

Current migrations cover:

- users
- posts
- comments
- likes
- feed index optimization
- optional `profile_image_url` on users

## Schema Layer

Location:

- `app/schemas`

Responsibilities:

- request validation
- response shaping
- keeping API contracts separate from ORM models

Important schema characteristics:

- feed endpoints return page objects instead of raw arrays
- authors include `profile_image_url`
- posts/comments expose ready-to-render state:
  - counts
  - `liked_by_me`
  - `likers_preview`

## Infrastructure Layer

Location:

- `app/core`
- `Dockerfile`
- `.github/workflows/deploy.yml`

Responsibilities:

- config loading
- password hashing and JWT
- Redis client lifecycle
- rate limiting
- deployment automation

Key modules:

- `config.py`
- `security.py`
- `redis.py`
- `rate_limit.py`

## Data Flow

### Auth flow

1. user registers
2. password is hashed before persistence
3. user logs in with email/password
4. backend returns JWT access token
5. protected routes resolve `CurrentUser` from bearer token

### Post compose flow

1. client sends multipart request to `POST /posts/compose`
2. endpoint accepts optional `content`
3. endpoint accepts optional `image`
4. if image exists, backend validates and uploads it to S3
5. service enforces that at least one of content or image exists
6. post is stored and reloaded for response serialization

### Feed read flow

1. authenticated user requests `GET /posts`
2. query filters by visibility
3. query computes:
   - like count
   - comment count
   - liked-by-me state
4. results are ordered by `(created_at desc, id desc)`
5. cursor pagination returns `items`, `next_cursor`, `has_more`
6. liker preview users are loaded for only the current page

### Comment read flow

1. authenticated user requests `GET /posts/{post_id}/comments`
2. service confirms post visibility first
3. top-level comments are loaded with cursor pagination
4. like count and liked-by-me are computed in SQL
5. replies are fetched for the current parent set
6. liker previews are loaded for visible comments and replies

### Upload flow

1. authenticated user uploads file
2. backend reads the bytes with a hard size cap
3. backend validates:
   - declared type
   - file signature
   - real image decode
   - pixel count
4. backend uploads the bytes to S3
5. public URL is returned

## Storage Design

### PostgreSQL

Primary relational store for:

- users
- posts
- comments
- post likes
- comment likes

Notable design points:

- foreign keys use cascading deletes
- likes use uniqueness constraints
- feed and comment paths use dedicated indexes
- post visibility is explicit in the database

### S3

Used for:

- post images
- profile images

Current pattern:

- backend-controlled uploads
- public-read access only for configured object prefixes
- URLs are stored directly on application records

### Redis / Valkey

Used for:

- rate limiting counters

Current pattern:

- FastAPI app opens Redis on startup
- write/auth endpoints use dependency-based rate limiting
- production is expected to use a network-reachable Redis or Valkey instance

## Domain Model Summary

### User

- owns posts
- owns comments
- owns likes
- may have optional `profile_image_url`

### Post

- belongs to a user
- can be `public` or `private`
- has text content and optional image URL
- exposes liker preview and aggregate state in responses

### Comment

- belongs to a post
- belongs to a user
- may reference a parent comment
- replies live in the same table

### PostLike / CommentLike

- connect users to target resources
- enforce uniqueness per user/resource pair

## Deployment Architecture

Deployment path:

1. push to `master`
2. GitHub Actions builds Docker image
3. image is pushed to ECR with a commit SHA tag
4. workflow SSHs into EC2
5. EC2 pulls the commit-SHA image
6. old container is stopped and removed
7. new container starts
8. workflow verifies:
   - correct image is running
   - `/health` becomes ready
9. cleanup prunes unused Docker artifacts and old host caches

This avoids silent drift between the Git commit and the container that actually runs.

## Scalability Notes

The codebase is still intentionally simple enough for a take-home project, but several implementation choices already push it toward better scale:

- cursor pagination for posts and comments
- DB-side aggregate computation for post/comment liked state and counts
- feed-specific indexes
- dedicated write-path rate limiting
- S3 media storage instead of local disk

Most likely future scaling steps:

- more automated tests around high-risk flows
- direct browser-to-S3 uploads with presigned URLs
- caching or denormalized counters if product needs justify them
- refresh-token based auth for longer-lived sessions

## Security Notes

Implemented security-oriented measures:

- password hashing
- JWT-protected routes
- visibility checks for private content
- protected upload endpoints
- Redis-backed rate limiting
- hardened image upload validation
- restricted S3 object-prefix exposure

Still intentionally simple:

- no refresh-token/session rotation yet
- no media lifecycle cleanup yet
- no direct CDN/private media layer yet
