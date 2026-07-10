# Social Publisher

Self-hosted social media publisher. Post to X, LinkedIn, and Threads from markdown files in a GitHub repo.

## How it works

```
1. Escribes un post en content/ como .md con frontmatter
2. GitHub Actions corre cada 30 min
3. Si hay posts programados para ahora, los publica
4. El post se mueve a content/published/
```

## Formato de un post

Crea un archivo `.md` en `content/`:

```markdown
---
date: 2026-07-20T13:00:00Z
platforms: [x, linkedin]
lang: en
---

Your post content here.

Can have multiple paragraphs.

For threads on X, split with ---

---

Second tweet of the thread

---

Third tweet of the thread
```

### Campos del frontmatter

| Campo | Requerido | Valores |
|-------|-----------|---------|
| `date` | ✅ | ISO 8601 (2026-07-20T13:00:00Z) |
| `platforms` | ✅ | `[x]`, `[linkedin]`, `[threads]`, `[x, linkedin]`, etc. |
| `lang` | ❌ | `en`, `es` (default: en) |

## Setup de APIs (lo haces UNA vez)

Necesitas crear developer apps en cada red y pasarme los tokens:

### X (Twitter)
1. Ve a https://developer.twitter.com → Sign in → Create Project
2. Crea una App dentro del proyecto
3. Genera estos tokens en "Keys and Tokens":
   - `API_KEY` (Consumer Key)
   - `API_SECRET` (Consumer Secret)
   - `ACCESS_TOKEN` (Access Token)
   - `ACCESS_TOKEN_SECRET` (Access Token Secret)

### LinkedIn
1. Ve a https://www.linkedin.com/developers → Create App
2. Nombra la app "Softgrama Publisher"
3. En Settings → Auth: copia `CLIENT_ID` y `CLIENT_SECRET`
4. En Products: solicita "Share on LinkedIn" y "Sign In with LinkedIn"
5. Ve a "OAuth 2.0 tools" → Generate Access Token

### Threads
1. Ve a https://developers.facebook.com → Create App → Business
2. Agrega "Threads API"
3. Ve a "Roles" → "Instagram Testers" → agrega tu cuenta
4. Ve a "Graph API Explorer" → genera token con permiso `threads_basic`

Una vez tengas los tokens, pásamelos y los configuro como GitHub Secrets.
