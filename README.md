# Social Feed API

FastAPI backend for a social feed application with JWT auth, PostgreSQL, S3-backed media, Redis-backed rate limiting, and Docker-based deployment to EC2.

## What It Supports

- user registration, login, and current-user lookup
- public and private posts
- comments and one-level replies
- like/unlike for posts, comments, and replies
- liker listing plus small liker previews for feed rendering
- cursor pagination for posts and comments
- S3-backed post image uploads
- optional user profile images
- multipart post composition with optional text and optional image

## Core Features

### Authentication

- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`

Auth uses JWT bearer tokens.

### Posts

- `POST /api/v1/posts`
  - existing JSON endpoint
  - expects text content
  - optional `image_url`
- `POST /api/v1/posts/compose`
  - new multipart endpoint
  - accepts optional `content`
  - accepts optional `image`
  - at least one of `content` or `image` must be present
  - uploads the image first, then creates the post
- `GET /api/v1/posts`
  - protected feed endpoint
  - newest first
  - cursor paginated

### Comments and Replies

- `POST /api/v1/posts/{post_id}/comments`
- `GET /api/v1/posts/{post_id}/comments`

Replies are stored in the same `comments` table using `parent_id`. Only one reply level is supported.

### Likes

- `POST /api/v1/posts/{post_id}/like`
- `DELETE /api/v1/posts/{post_id}/like`
- `GET /api/v1/posts/{post_id}/likes`
- `POST /api/v1/comments/{comment_id}/like`
- `DELETE /api/v1/comments/{comment_id}/like`
- `GET /api/v1/comments/{comment_id}/likes`

### Uploads and Profile Images

- `POST /api/v1/uploads/post-image`
- `POST /api/v1/users/me/profile-image`

The backend uploads media to S3 and returns public URLs for configured prefixes.

## Response Shape Highlights

### Feed page

`GET /api/v1/posts` returns:

```json
{
  "items": [],
  "next_cursor": "opaque-cursor",
  "has_more": true
}
```

Each post includes:

- `like_count`
- `comment_count`
- `liked_by_me`
- `likers_preview`
- `author.profile_image_url`

### Comment page

`GET /api/v1/posts/{post_id}/comments` returns:

```json
{
  "items": [],
  "next_cursor": "opaque-cursor",
  "has_more": true
}
```

Each comment and reply includes:

- `like_count`
- `liked_by_me`
- `likers_preview`
- `author.profile_image_url`

## Tech Stack

- FastAPI
- PostgreSQL
- SQLAlchemy 2.0 async ORM
- Alembic
- Redis / Valkey
- Amazon S3
- Pillow
- Docker
- GitHub Actions
- Amazon ECR
- Amazon EC2

## Data Model Summary

### User

- first name
- last name
- email
- password hash
- optional `profile_image_url`
- active state
- timestamps

### Post

- author
- non-null `content`
- optional `image_url`
- visibility: `public` or `private`
- timestamps

The multipart compose endpoint allows image-only posts by saving an empty string in `content` when needed.

### Comment

- post reference
- author reference
- optional `parent_id`
- content
- timestamps

### PostLike

- post reference
- user reference
- unique `(post_id, user_id)`

### CommentLike

- comment reference
- user reference
- unique `(comment_id, user_id)`

## Security and Performance Choices

- passwords are hashed before storage
- JWT protects write/read endpoints that require auth
- private posts are filtered in query logic
- upload endpoints are protected
- Redis-backed rate limiting is applied to auth and write-heavy routes
- image uploads are validated by:
  - size
  - MIME type
  - file signature
  - real image decode
  - pixel count
- feed and comment responses use DB-side aggregation for counts and liked-state
- feed and comments use cursor pagination instead of offset pagination

## Environment Variables

Example `.env`:

```env
APP_NAME=Social Feed API
ENVIRONMENT=local
DEBUG=False
API_V1_PREFIX=/api/v1

SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=120

DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/social_feed
SYNC_DATABASE_URL=postgresql+psycopg://postgres:password@localhost:5432/social_feed

CORS_ORIGINS=http://localhost:3000,http://localhost:5173

AWS_REGION=ap-south-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_SESSION_TOKEN=
S3_BUCKET_NAME=your-bucket-name
S3_PUBLIC_BASE_URL=https://your-bucket-name.s3.ap-south-1.amazonaws.com
S3_ENDPOINT_URL=
S3_OBJECT_PREFIX=post-images
S3_PROFILE_IMAGE_PREFIX=profile-images
MAX_IMAGE_UPLOAD_BYTES=10485760
MAX_IMAGE_PIXELS=25000000

REDIS_URL=redis://localhost:6379/0
RATE_LIMIT_ENABLED=true

RATE_LIMIT_AUTH_LOGIN_MAX_REQUESTS=10
RATE_LIMIT_AUTH_LOGIN_WINDOW_SECONDS=60
RATE_LIMIT_AUTH_REGISTER_MAX_REQUESTS=5
RATE_LIMIT_AUTH_REGISTER_WINDOW_SECONDS=900
RATE_LIMIT_POST_WRITE_MAX_REQUESTS=20
RATE_LIMIT_POST_WRITE_WINDOW_SECONDS=60
RATE_LIMIT_COMMENT_WRITE_MAX_REQUESTS=40
RATE_LIMIT_COMMENT_WRITE_WINDOW_SECONDS=60
RATE_LIMIT_LIKE_WRITE_MAX_REQUESTS=120
RATE_LIMIT_LIKE_WRITE_WINDOW_SECONDS=60
RATE_LIMIT_UPLOAD_MAX_REQUESTS=10
RATE_LIMIT_UPLOAD_WINDOW_SECONDS=300
```

For ElastiCache / Valkey with in-transit encryption enabled, use a `rediss://...` URL in production.

## Local Development

### 1. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Start PostgreSQL and Redis locally

If you use Docker for Redis:

```bash
docker run -d --name social-feed-redis -p 6379:6379 redis:7-alpine
```

### 4. Run migrations

```bash
alembic upgrade head
```

### 5. Start the app

```bash
uvicorn app.main:app --reload
```

### 6. Open docs

```text
http://127.0.0.1:8000/docs
```

## Docker

Build:

```bash
docker build -t social-feed-api .
```

Run:

```bash
docker run -p 8000:8000 --env-file .env social-feed-api
```

Container startup runs Alembic before starting Uvicorn.

## Deployment

Deployment path:

1. push to `master`
2. GitHub Actions builds a Docker image
3. image is pushed to ECR with both commit SHA and `latest` tags
4. EC2 pulls the commit-SHA image
5. container starts with the server `.env`
6. the workflow verifies the running image and waits for `/health`
7. Docker and host cleanup runs after a successful deployment

## Current Limitations

- replies are limited to one level
- post content is still stored as non-null text in the database
- avatar replacement does not delete the old S3 object
- uploads are backend-proxied rather than direct browser-to-S3
- automated test coverage can still be expanded

## Suggested Next Improvements

- add high-value API tests for auth, posts, comments, likes, uploads, and rate limiting
- add refresh-token based auth if longer-lived sessions are needed
- add direct-to-S3 presigned upload flow for higher throughput
- add cleanup for replaced profile images and post images if desired
