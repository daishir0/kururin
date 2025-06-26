// トグルボタンにクリックイベントリスナーを追加
document.querySelector('.toggle-button').addEventListener('click', toggleSidebar);

// サイドバーの開閉を制御する関数
function toggleSidebar() {
    var sidebar = document.getElementById("sidebar");
    var toggleButton = document.querySelector('.toggle-button');

    // サイドバーが開いているか閉じているかをチェック
    var isSidebarOpen = sidebar.style.left === "0px";

    // サイドバーとボタンの位置を切り替える
    if (isSidebarOpen) {
        // サイドバーを閉じる
        sidebar.style.left = "-250px"; // サイドバーを左に隠す
        toggleButton.style.transform = "none"; // トグルボタンの位置をリセット
    } else {
        // サイドバーを開く
        sidebar.style.left = "0px"; // サイドバーを表示
        toggleButton.style.transform = "translateX(250px)"; // トグルボタンを右に移動
    }
}

// ページロード時にサイドバーを閉じるための初期化処理
function closeSidebarInitially() {
    var sidebar = document.getElementById("sidebar");
    sidebar.style.left = "-250px"; // サイドバーを左に隠す
}

// 新規録音ボタンにイベントリスナーを追加
document.getElementById('reflesh-new').addEventListener('click', function() {
    window.location.reload(); // ページを再読み込み
});

// 初期化処理を実行
closeSidebarInitially();
