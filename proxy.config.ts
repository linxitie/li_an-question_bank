export default {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
    ws: true
  },
  '/static': {
    target: 'http://localhost:8000',
    changeOrigin: true
  },
  '/uploads': {
    target: 'http://localhost:8000',
    changeOrigin: true
  }
};
