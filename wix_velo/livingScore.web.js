import { webMethod, Permissions } from 'wix-web-module';
import { fetch } from 'wix-fetch';

// Replace this after deploying the Nazufi backend.
const API_BASE = 'https://YOUR-API-DOMAIN.example';

function normalisePostcode(postcode) {
  return String(postcode || '')
    .trim()
    .toUpperCase()
    .replace(/\s+/g, ' ');
}

function safeError(message, code = 'UPSTREAM_UNAVAILABLE') {
  return {
    ok: false,
    error: code,
    message
  };
}

export const getAreaReport = webMethod(
  Permissions.Anyone,
  async (postcode) => {
    const pc = normalisePostcode(postcode);

    if (!pc || pc.length < 5 || pc.length > 8) {
      return safeError('Please enter a valid UK postcode format.', 'INVALID_POSTCODE');
    }

    try {
      const response = await fetch(
        `${API_BASE}/area-report/${encodeURIComponent(pc)}`,
        {
          method: 'GET',
          headers: {
            'Accept': 'application/json'
          }
        }
      );

      if (!response.ok) {
        return safeError(
          `The validated data service returned ${response.status}.`,
          'UPSTREAM_ERROR'
        );
      }

      const report = await response.json();

      // Never create fallback values here.
      // Missing values must stay unavailable.
      return {
        ok: true,
        report
      };
    } catch (error) {
      return safeError(
        'The data service is temporarily unavailable. No substitute values were generated.',
        'NETWORK_ERROR'
      );
    }
  }
);

export const getDataFreshness = webMethod(
  Permissions.Anyone,
  async () => {
    try {
      const response = await fetch(`${API_BASE}/freshness`, {
        method: 'GET',
        headers: {
          'Accept': 'application/json'
        }
      });

      if (!response.ok) {
        return safeError(
          `The freshness service returned ${response.status}.`,
          'UPSTREAM_ERROR'
        );
      }

      return {
        ok: true,
        freshness: await response.json()
      };
    } catch (error) {
      return safeError(
        'Source freshness is temporarily unavailable.',
        'NETWORK_ERROR'
      );
    }
  }
);
