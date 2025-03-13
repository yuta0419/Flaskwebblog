// static/js/script.js

document.addEventListener("DOMContentLoaded", function() {
  // Bootstrapのアラートは自動で閉じる機能は無いので、カスタムで実装
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(alert => {
    setTimeout(() => {
      // Bootstrap 5 の Alert API を利用して閉じる
      // ※ bsAlert が利用可能か確認してください（CDNで読み込んでいるため通常はOK）
      var bsAlert = new bootstrap.Alert(alert);
      bsAlert.close();
    }, 5000); // 5秒後に閉じる
  });
});
