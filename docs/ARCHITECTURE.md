# Architecture

## Overview

This project is a layered FastAPI backend for a social feed application. The system is structured to keep HTTP concerns, business rules, persistence, and schema definitions separated so the codebase stays readable and easier to extend.

The backend currently supports:
- JWT-based authentication
- public and private posts
- comments and one-level replies
- like and unlike flows for posts and comments
- liker visibility endpoints
- S3-backed image uploads

## Architectural Style

The project follows a service-oriented layered architecture:

1. API layer
2. service layer
3. persistence layer
4. schema layer
5. infrastructure/config layer

This keeps route handlers thin and moves business logic into reusable service functions.

## Layer Breakdown

### API Layer

Location:
- `app/api/routes`
- `app/api/router.py`
- `app/api/deps.py`

Responsibilities:
- define endpoints
- accept request payloads
- apply auth dependencies
- translate domain errors into HTTP responses
- return response schemas

Examples:
- `auth.py`
- `post.py`
- `comment.py`
- `like.py`
- `upload.py`

### Service Layer

Location:
- `app/services`

Responsibilities:
- implement business rules
- enforce visibility checks
- handle create/list/like/unlike workflows
- orchestrate S3 upload behavior

Examples:
- `user_service.py`
- `post_service.py`
- `comment_service.py`
- `like_service.py`
- `storage_service.py`

This layer is the core of the application behavior.

### Persistence Layer

Location:
- `app/models`
- `app/db`
- `alembic`

Responsibilities:
- relational modeling
- async database session management
- schema migrations

The application uses:
- PostgreSQL for relational data
- SQLAlchemy 2.0 async ORM
- Alembic for migrations

### Schema Layer

Location:
- `app/schemas`

Responsibilities:
- validate request bodies
- define response contracts
- separate API shape from ORM shape

This helps avoid leaking raw ORM objects directly into the API surface.

### Infrastructure and Config Layer

Location:
- `app/core`
- Docker and GitHub workflow files

Responsibilities:
- environment configuration
- JWT helpers and password hashing
- deployment/runtime behavior

## Data Storage Design

### PostgreSQL

Primary relational store for:
- users
- posts
- comments
- post likes
- comment likes

Key design choices:
- UUID primary keys
- foreign keys with cascading deletes
- unique constraints for likes
- indexes on feed-related lookup paths

### Amazon S3

Used for uploaded post images.

Flow:
1. authenticated user uploads image through backend
2. backend validates and uploads to S3
3. returned public URL is stored in `posts.image_url`

## Authentication and Authorization

Authentication is JWT-based.

Flow:
1. user registers
2. user logs in with email and password
3. backend returns access token
4. protected endpoints use bearer token authentication

Authorization is enforced in service-layer query logic, especially for:
- private posts
- comments on private posts
- like visibility on private resources

## Domain Model Summary

### User
- owns posts
- owns comments
- owns likes

### Post
- belongs to one user
- can be `public` or `private`
- can have many comments
- can have many likes

### Comment
- belongs to one post
- belongs to one user
- may optionally reference a parent comment

Replies are stored in the same table using `parent_id`.

### PostLike
- connects one user to one post
- unique per `(post_id, user_id)`

### CommentLike
- connects one user to one comment
- unique per `(comment_id, user_id)`

## Deployment Architecture

Deployment path:
1. push code to GitHub
2. GitHub Actions builds Docker image
3. image is pushed to Amazon ECR
4. workflow connects to EC2 over SSH
5. EC2 pulls and runs the new container
6. Alembic migrations run on container startup

The application is therefore deployed as a single containerized API service backed by PostgreSQL and S3.

## Scalability Notes

The current implementation is correct and feature-complete for assignment/demo scale.

Important future improvements for higher scale:
- replace offset pagination with cursor pagination
- compute feed counts through DB-side aggregates instead of Python-side relationship loading
- reduce over-fetching on feed endpoints
- add rate limiting
- move to direct-to-S3 presigned uploads for higher upload throughput

## Security Notes

Current security-oriented choices include:
- password hashing
- JWT-protected routes
- private post visibility enforcement
- protected upload endpoint
- S3 image uploads scoped by backend logic

Recommended next-step hardening:
- rate limiting for auth and write-heavy endpoints
- stronger file-content validation for uploads
- broader automated test coverage
- least-privilege IAM role usage on EC2
