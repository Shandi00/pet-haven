/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      // 配色取自期末專題提案簡報：主色暖橘、文字與深色區塊用暖咖啡、底色用暖灰。
      // 品牌色一律用 primary，不要再直接寫 blue／purple／orange。
      // 白字按鈕用 primary-600 以上（對白色對比 ≥ 4.5，符合 WCAG AA）；primary-500 是簡報主橘，用於圖示、外框、大色塊。
      colors: {
        primary: {
          50: '#fdf3ec',
          100: '#fce6d6',
          200: '#f9cdb0',
          300: '#f4a970',
          400: '#ee8a47',
          500: '#e8702a',
          600: '#b4501f',
          700: '#9c461b',
          800: '#7d3816',
          900: '#5f2b12',
        },
        // 覆蓋 Tailwind 預設的冷灰，改成簡報的暖灰咖啡色階（gray-500 起對白色對比 ≥ 4.5）
        gray: {
          50: '#faf9f8',
          100: '#f3f1ef',
          200: '#e7e4e3',
          300: '#cecac8',
          400: '#a9a5a2',
          500: '#726c68',
          600: '#605956',
          700: '#47403c',
          800: '#3e2c23',
          900: '#2e2622',
        },
        secondary: {
          50: '#fef2f2',
          100: '#fee2e2',
          200: '#fecaca',
          300: '#fca5a5',
          400: '#f87171',
          500: '#ef4444',
          600: '#dc2626',
          700: '#b91c1c',
          800: '#991b1b',
          900: '#7f1d1d',
        }
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'Noto Sans', 'sans-serif'],
      },
      animation: {
        'fade-in': 'fadeIn 0.5s ease-in-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'bounce-slow': 'bounce 2s infinite',
        // 配對小遊戲（T10）：選項打勾、腳印進度、小狗跳一下、結果揭曉的彩帶。一律搭配 motion-safe: 使用
        'pop-in': 'popIn 0.35s cubic-bezier(0.34, 1.56, 0.64, 1)',
        'hop': 'hop 0.5s ease-out',
        'confetti': 'confetti 1.6s ease-in forwards',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
        popIn: {
          '0%': { transform: 'scale(0.5)', opacity: '0' },
          '100%': { transform: 'scale(1)', opacity: '1' },
        },
        hop: {
          '0%, 100%': { transform: 'translateY(0) rotate(0deg)' },
          '40%': { transform: 'translateY(-8px) rotate(-6deg)' },
          '70%': { transform: 'translateY(0) rotate(4deg)' },
        },
        // --drift 由每片彩帶自己設定，讓落下時左右飄的距離不同
        confetti: {
          '0%': { transform: 'translate3d(0, -12px, 0) rotate(0deg)', opacity: '1' },
          '100%': { transform: 'translate3d(var(--drift, 0px), 360px, 0) rotate(540deg)', opacity: '0' },
        },
      }
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
}