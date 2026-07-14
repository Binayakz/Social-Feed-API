# Social Feed API

A backend API for a social feed application built with FastAPI and PostgreSQL. The system supports secure authentication, protected feeds, public/private posts, comments with one-level replies, like/unlike flows, liker visibility, and S3-based image uploads.

## Features

### Authentication
- User registration with:
  - first name
  - last name
  - email
  - password
- JWT-based login
- Protected current-user endpoint

### Posts
- Create posts with text
- Optional image support through uploaded image URLs
- Public and private post visibility
- Feed ordered with newest posts first

### Comments and Replies
- Add comments to posts
- Add one-level replies to comments
- List comments for a post

### Likes
- Like/unlike posts
- Like/unlike comments
- Like/unlike replies
- List users who liked a post
- List users who liked a comment or reply

### Uploads
- Protected image upload endpoint
- S3-backed file storage
- Returned image URL can be used in post creation

## Tech Stack

- FastAPI
- PostgreSQL
- SQLAlchemy 2.0 (async)
- Alembic
- JWT authentication
- Passlib
- Amazon S3
- Docker
- GitHub Actions
- EC2
- ECR

## Project Structure

```text
app/
  api/
    deps.py
    router.py
    routes/
  core/
    config.py
    security.py
  db/
    base.py
    session.py
  models/
  schemas/
  services/
alembic/
.github/workflows/
Dockerfile
requirements.txt
README.md
```

## Data Model Overview

### User
Stores:
- name
- email
- password hash
- active state
- timestamps

### Post
Stores:
- author
- content
- optional image URL
- visibility (`public` or `private`)
- timestamps

### Comment
Stores:
- post reference
- author reference
- optional `parent_id`
- content
- timestamps

Replies are implemented using the same `comments` table through a self-referential `parent_id`.

### PostLike
Stores:
- post reference
- user reference
- unique `(post_id, user_id)` pair

### CommentLike
Stores:
- comment reference
- user reference
- unique `(comment_id, user_id)` pair

## API Summary

Base prefix:

```text
/api/v1
```

### Auth
- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`

### Posts
- `POST /posts`
- `GET /posts`

### Comments
- `POST /posts/{post_id}/comments`
- `GET /posts/{post_id}/comments`

### Likes
- `POST /posts/{post_id}/like`
- `DELETE /posts/{post_id}/like`
- `GET /posts/{post_id}/likes`

- `POST /comments/{comment_id}/like`
- `DELETE /comments/{comment_id}/like`
- `GET /comments/{comment_id}/likes`

### Uploads
- `POST /uploads/post-image`

## Environment Variables

Create a `.env` file with the following values:

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
S3_BUCKET_NAME=your-bucket-name
S3_PUBLIC_BASE_URL=https://your-bucket-name.s3.ap-south-1.amazonaws.com
S3_OBJECT_PREFIX=post-images
MAX_IMAGE_UPLOAD_BYTES=10485760
```

Optional:

```env
AWS_SESSION_TOKEN=
S3_ENDPOINT_URL=
```

## Local Development Setup

### 1. Create virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run migrations

```bash
alembic upgrade head
```

### 4. Start the app

```bash
uvicorn app.main:app --reload
```

### 5. Open API docs

```text
http://127.0.0.1:8000/docs
```

## Docker

Build image:

```bash
docker build -t social-feed-api .
```

Run container:

```bash
docker run -p 8000:8000 --env-file .env social-feed-api
```

The container startup command runs Alembic migrations automatically before starting Uvicorn.

## Deployment

The project is deployed through GitHub Actions to an EC2 instance.

Deployment flow:
1. GitHub Actions builds Docker image
2. Pushes image to Amazon ECR
3. Connects to EC2 over SSH
4. Pulls the latest image
5. Starts container with server `.env`
6. Runs migrations on container startup

## Security Notes

- Passwords are hashed before storage
- JWT is used for protected routes
- Private posts are only visible to their author
- Comments and likes on private posts are visibility-checked
- Upload endpoint is protected
- S3 write access is backend-controlled
- Uploaded images are served through a restricted public prefix strategy

## Scalability Notes

The current implementation is designed to be correct and feature-complete for the assignment and moderate usage.

Important future improvements for very large scale:
- replace offset pagination with cursor pagination
- move `like_count`, `comment_count`, and `liked_by_me` computations into DB-side aggregate queries
- add rate limiting for auth, uploads, comments, and likes
- expand automated testing coverage
- consider direct-to-S3 presigned uploads for heavier upload workloads

## Design Choices

- UUID primary keys are used for major entities
- replies are stored in the `comments` table using `parent_id`
- likes are split into `post_likes` and `comment_likes`
- uploads are separate from post creation:
  1. upload image
  2. receive URL
  3. create post with `image_url`

## Current Limitations

- replies are limited to one level
- feed pagination currently uses offset/limit
- some response counts are computed in application logic rather than SQL aggregates
- rate limiting is not yet implemented
- tests should be expanded for production-grade confidence

## Future Improvements

- DB-optimized feed aggregation
- cursor pagination
- rate limiting
- direct presigned uploads
- richer moderation/reporting support
- broader automated tests
- CloudFront/private-media delivery if needed

## Submission Notes

This backend was built to satisfy the core functional requirements of:
- authentication and authorization
- protected feed
- public/private posts
- comments and replies
- like/unlike behavior
- show who liked
- image upload support

Frontend/UI implementation is intentionally separate from this backend repository.
