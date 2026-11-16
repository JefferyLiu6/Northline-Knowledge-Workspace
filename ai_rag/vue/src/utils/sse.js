/**
 * Send and parse streaming SSE requests.
 *
 * EventSource supports GET requests and does not let callers set request headers.
 * The Q&A endpoint uses POST and requires an auth token, so this client parses the stream returned by fetch.
 *
 * An empty line separates SSE events.
 *
 *     event: delta
 *     data: {"text":"Quality"}
 *
 *     event: delta
 *     data: {"text":"Guarantee"}
 */
import { ElMessage } from 'element-plus'

const baseUrl = import.meta.env.VITE_BASE_URL

/**
 * Start a streaming Q&A request.
 *
 * @param {string} path     Endpoint path, such as /qaApp/ask
 * @param {object} body     Request body
 * @param {function} onEvent Called once for each complete event with the event name and parsed data
 */
export async function streamPost(path, body, onEvent) {
  // Token took from the cache stored at the time of entry and shared with request interceptors for request.js
  const user = JSON.parse(localStorage.getItem('xm-user') || '{}')
  const response = await fetch(baseUrl + path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json;charset=utf-8',
      token: user.token || ''
    },
    body: JSON.stringify(body)
  })
  if (!response.ok) {
    ElMessage.error('Request Failed, Please Check Backend Console Error')
    return
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  // The last half of the missing papers were read, and this time they're put together to sort them out.
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) {
      break
    }
    // SSE supports CRLF, LF, and CR line endings. sse-starlette sends CRLF.
    // Normalize line endings to LF so blank lines separate events consistently.
    // There's no event on the page, and the back end is actually running out of time and keeping the news in the dark.
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n?/g, '\n')
    // The empty line is the end sign of an event.
    const blocks = buffer.split('\n\n')
    // The last one could be broken. Save it for the next round.
    buffer = blocks.pop()
    for (const block of blocks) {
      const parsed = parseBlock(block)
      if (parsed) {
        onEvent(parsed.event, parsed.data)
      }
    }
  }
}

/**
 * Parse an SSE event name and its data.
 */
function parseBlock(block) {
  let event = 'message'
  const dataLines = []
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim()
    } else if (line.startsWith('data:')) {
      // One incident, Data, could be a good one.
      dataLines.push(line.slice(5).trim())
    }
  }
  if (!dataLines.length) {
    return null
  }
  try {
    return { event, data: JSON.parse(dataLines.join('')) }
  } catch (error) {
    // The back end is not legal. JSON skips this part and doesn't break the whole stream.
    return null
  }
}
