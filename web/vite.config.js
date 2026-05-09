import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// Pages deploys to https://hildieleyser.github.io/auracle/, so production
// assets need the /auracle/ prefix. Local dev serves from /.
export default defineConfig(({ command }) => ({
  base: command === 'build' ? '/auracle/' : '/',
  plugins: [react(), tailwindcss()],
}));
