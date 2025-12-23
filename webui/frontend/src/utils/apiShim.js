import { request } from '../lib/api';

function buildUrl(url, params = {}) {
  if (!params || typeof params !== 'object') {
    return url;
  }

  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null) {
      return;
    }
    if (Array.isArray(value)) {
      value.forEach((entry) => {
        searchParams.append(key, String(entry));
      });
    } else {
      searchParams.append(key, String(value));
    }
  });

  if (!searchParams.toString()) {
    return url;
  }

  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}${searchParams.toString()}`;
}

function wrapResponse(data) {
  return { data };
}

async function call(url, method, payload, config = {}) {
  const { params, ...rest } = config || {};
  const options = { ...rest };
  if (method) {
    options.method = method;
  }
  if (payload !== undefined) {
    options.body = payload;
  }

  const finalUrl = buildUrl(url, params);
  const data = await request(finalUrl, options);
  return wrapResponse(data);
}

const apiShim = {
  get(url, config) {
    return call(url, 'GET', undefined, config);
  },
  delete(url, config) {
    return call(url, 'DELETE', undefined, config);
  },
  post(url, data, config) {
    return call(url, 'POST', data, config);
  },
  put(url, data, config) {
    return call(url, 'PUT', data, config);
  },
  patch(url, data, config) {
    return call(url, 'PATCH', data, config);
  },
};

export default apiShim;
