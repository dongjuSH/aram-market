// 상품 목록 하단 페이지 이동 및 등록 버튼 UI

// 동작 연결 전 페이지 이동 및 상품 등록 UI
function ProductPagination() {
  return (
    <div className="product-footer">
      <nav className="pagination" aria-label="상품 목록 페이지">
        <button type="button" aria-label="이전 페이지">‹</button>
        <button className="is-current" type="button" aria-current="page">1</button>
        <button type="button">2</button>
        <button type="button">3</button>
        <button type="button">4</button>
        <button type="button">5</button>
        <button type="button" aria-label="다음 페이지">›</button>
      </nav>
      <button className="product-create" type="button"><span aria-hidden="true">＋</span> 상품 등록</button>
    </div>
  )
}

export default ProductPagination
