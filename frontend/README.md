# AE Scientist - Frontend

A modern Next.js web application for managing research conversations and generating AI-guided project proposals.

## Overview

The frontend provides an intuitive interface for:
- **Conversation Management**: Import and view LLM conversations from various providers
- **Project Drafting**: Generate and refine structured research proposals through interactive dialogue
- **Version Control**: Track changes to project drafts with visual diff viewers
- **Search**: Semantic search across conversations and projects
- **File Management**: Upload and attach images and PDFs to conversations

## Tech Stack

- **Framework**: Next.js 15 with React 19
- **Language**: TypeScript 5
- **Styling**: Tailwind CSS 4
- **Markdown**: react-markdown with KaTeX for math rendering
- **API Types**: Auto-generated from backend OpenAPI schema

## Setup

### Prerequisites

- Node.js 20 or higher
- npm or pnpm
- Running backend server (see `../server/README.md`)

### Installation

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Configure environment variables**:
   ```bash
   cp env.local.example .env.local
   ```

3. **Edit `.env.local`** with your configuration:
   ```bash
   # API Configuration
   NEXT_PUBLIC_API_BASE_URL="http://localhost:8000"
   
   # Development Settings  
   NEXT_PUBLIC_ENVIRONMENT="development"

   # Stripe Checkout
   NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY="pk_test_xxx"

   # Credit gates (mirror backend thresholds)
   NEXT_PUBLIC_MIN_USER_CREDITS_FOR_CONVERSATION="10"
   NEXT_PUBLIC_MIN_USER_CREDITS_FOR_RESEARCH_PIPELINE="25"
   ```

   - `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` is required for redirecting users to Stripe Checkout.
   - `NEXT_PUBLIC_MIN_USER_CREDITS_FOR_*` keep the UI in sync with backend credit thresholds so buttons can disable before the API gate fires.

### Development

Start the development server:
```bash
npm run dev
```

The application will be available at [http://localhost:3000](http://localhost:3000)

## Available Scripts

### Development
```bash
npm run dev              # Start development server with Turbopack
npm run build            # Build for production
npm run start            # Start production server
```

### Code Quality
```bash
npm run lint             # Run ESLint
npm run lint:fix         # Fix ESLint issues automatically
npm run format           # Format code with Prettier
npm run format:check     # Check code formatting without changes
npm run style            # Lint and fix CSS with Stylelint
```

### API Types
```bash
npm run gen:api-types              # Generate types from running backend
npm run gen:api-types:from-file    # Generate types from backend/openapi.json
```

**Note**: Types are automatically regenerated during build via the `prebuild` script.

### Tailwind Utilities
```bash
npm run check-tailwind   # Check for Tailwind CSS issues
npm run fix-tailwind     # Fix Tailwind issues and restart dev server
```

## Type Generation

The frontend maintains type safety through auto-generated API types:

1. **During Development**: 
   - Run `npm run gen:api-types` to regenerate types from running backend
   - Types update automatically when backend OpenAPI schema changes

2. **During Build**:
   - `prebuild` script generates types from `../backend/openapi.json`
   - Ensures type consistency in production builds

3. **Type Usage**:
   ```typescript
   import type { components } from '@/types/api.gen';
   
   type Conversation = components['schemas']['Conversation'];
   ```

## Development Guidelines

### API Calls

Always use the generated types for API interactions:

```typescript
import type { paths } from '@/types/api.gen';

type ConversationsResponse = 
  paths['/api/conversations']['get']['responses']['200']['content']['application/json'];
```

