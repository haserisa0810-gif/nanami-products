// 注文番号・Order ID 入力欄の前後空白を、入力された時点で取り除く。
//
// 購入確認メールからコピペすると末尾に空白が混ざることがあり、そのままだと
// pattern 属性の検証で「指定されている形式で入力してください。」になって送信できない。
// サーバー側は _normalize_stores_order_no() が strip してから照合するので、
// クライアント側の正規化をそれにそろえる。
//
// 対象は data-trim-order-code を付けた input。
(function () {
  'use strict';

  var SELECTOR = 'input[data-trim-order-code]';

  function trimField(input) {
    var trimmed = input.value.replace(/^\s+|\s+$/g, '');
    if (trimmed === input.value) return;
    var caretAtEnd = input.selectionStart === input.value.length;
    input.value = trimmed;
    if (caretAtEnd) {
      try {
        input.setSelectionRange(trimmed.length, trimmed.length);
      } catch (e) {
        // 一部ブラウザで setSelectionRange 非対応の型があるため無視する。
      }
    }
  }

  function init() {
    document.querySelectorAll(SELECTOR).forEach(function (input) {
      input.addEventListener('input', function () { trimField(input); });
      input.addEventListener('blur', function () { trimField(input); });
    });
    // JSでsubmitするフォームもあるため、送信直前にもう一度そろえる。
    document.querySelectorAll('form').forEach(function (form) {
      form.addEventListener('submit', function () {
        form.querySelectorAll(SELECTOR).forEach(trimField);
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
