// static/js/index.js

const { createApp } = Vue;

// Vueアプリケーションをマウントする要素と、APIのURLを取得
const appElement = document.getElementById('app');
const statsUrl = appElement.dataset.statsUrl; // 'data-stats-url'の値を取得

createApp({
    data() {
        return {
            totalPapers: 0,
            totalSearches: 0,
            totalBookmarks: 0
        }
    },
    // ページ表示後にAPIを叩いて統計情報を取得
    mounted() {
        this.loadStats();
    },
    methods: {
        async loadStats() {
            try {
                // HTMLから受け取ったURLを使ってAPIを呼び出す
                const response = await fetch(statsUrl);

                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                const data = await response.json();

                // 取得したデータで画面を更新 (数値はカンマ区切りに)
                this.totalPapers = data.totalPapers.toLocaleString();
                this.totalSearches = data.totalSearches.toLocaleString();
                this.totalBookmarks = data.totalBookmarks.toLocaleString();

            } catch (error) {
                console.error('There has been a problem with your fetch operation:', error);
                // エラー時はメッセージを表示
                this.totalPapers = '取得失敗';
                this.totalSearches = '取得失敗';
                this.totalBookmarks = '取得失敗';
            }
        }
    }
}).mount('#app');