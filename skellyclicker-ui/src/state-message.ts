export const stateKind = {
  parse(message: unknown): {ready: boolean} {
    if (message === null || typeof message !== 'object'
      || !('application' in message) || message.application !== 'skellyclicker'
      || !('mode' in message) || message.mode !== 'playback'
      || !('ready' in message) || typeof message.ready !== 'boolean') {
      throw new Error('Invalid SkellyClicker state message');
    }
    return {ready: message.ready};
  },
};
