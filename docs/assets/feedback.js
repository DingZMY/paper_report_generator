(function(global) {
  const CLIENT_ID_KEY = 'bio-digest-client-id';
  const FEEDBACK_QUEUE_KEY = 'bio-digest-feedback-queue';
  const FEEDBACK_ENDPOINT_KEY = 'bio-digest-feedback-endpoint';
  const LOCAL_DEFAULT_ENDPOINT = 'http://127.0.0.1:8787/api/feedback/events';
  const SAME_ORIGIN_ENDPOINT = '/api/feedback/events';

  function readJson(key, fallback) {
    try {
      const value = global.localStorage.getItem(key);
      return value ? JSON.parse(value) : fallback;
    } catch {
      return fallback;
    }
  }

  function writeJson(key, value) {
    global.localStorage.setItem(key, JSON.stringify(value));
  }

  function getClientId() {
    let clientId = global.localStorage.getItem(CLIENT_ID_KEY);
    if (clientId) return clientId;

    clientId = global.crypto && typeof global.crypto.randomUUID === 'function'
      ? global.crypto.randomUUID()
      : 'client-' + Date.now() + '-' + Math.random().toString(16).slice(2);
    global.localStorage.setItem(CLIENT_ID_KEY, clientId);
    return clientId;
  }

  function setFeedbackEndpoint(endpoint) {
    if (!endpoint) {
      global.localStorage.removeItem(FEEDBACK_ENDPOINT_KEY);
      return;
    }
    global.localStorage.setItem(FEEDBACK_ENDPOINT_KEY, endpoint);
  }

  function getFeedbackEndpoint() {
    const configured = global.BIO_DIGEST_FEEDBACK_ENDPOINT || global.localStorage.getItem(FEEDBACK_ENDPOINT_KEY);
    if (configured) return configured;

    if (global.location.hostname === '127.0.0.1' || global.location.hostname === 'localhost') {
      return LOCAL_DEFAULT_ENDPOINT;
    }

    if (global.location.protocol === 'http:' || global.location.protocol === 'https:') {
      return global.location.origin + SAME_ORIGIN_ENDPOINT;
    }

    return '';
  }

  function getQueue() {
    return readJson(FEEDBACK_QUEUE_KEY, []);
  }

  function saveQueue(queue) {
    writeJson(FEEDBACK_QUEUE_KEY, queue);
  }

  function buildEvent(signal, action, paper, options) {
    const metadata = (options && options.metadata) || {};
    return {
      schema_version: 'feedback-event.v1',
      signal: signal,
      action: action,
      pmid: paper && paper.pmid ? String(paper.pmid) : '',
      week: paper && paper.week ? String(paper.week) : '',
      title: paper && paper.title ? String(paper.title) : '',
      journal: paper && paper.journal ? String(paper.journal) : '',
      timestamp: new Date().toISOString(),
      client_id: getClientId(),
      source_path: global.location.pathname,
      source_page: (options && options.sourcePage) || document.title,
      metadata: metadata,
    };
  }

  function enqueue(event) {
    const queue = getQueue();
    queue.push(event);
    saveQueue(queue);
    return event;
  }

  async function flushQueue() {
    const endpoint = getFeedbackEndpoint();
    const queue = getQueue();

    if (!endpoint || !queue.length || typeof global.fetch !== 'function') {
      return {
        sent: 0,
        remaining: queue.length,
      };
    }

    let sent = 0;
    while (queue.length) {
      try {
        const response = await global.fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(queue[0]),
          keepalive: true,
          mode: 'cors',
        });
        if (!response.ok) break;
      } catch {
        break;
      }

      queue.shift();
      sent += 1;
    }

    saveQueue(queue);
    return {
      sent: sent,
      remaining: queue.length,
    };
  }

  function track(signal, action, paper, options) {
    const event = enqueue(buildEvent(signal, action, paper || {}, options));
    void flushQueue();
    return event;
  }

  global.BioDigestFeedback = {
    track: track,
    flushQueue: flushQueue,
    getQueueSize: function() {
      return getQueue().length;
    },
    getFeedbackEndpoint: getFeedbackEndpoint,
    setFeedbackEndpoint: setFeedbackEndpoint,
    getClientId: getClientId,
  };
})(window);