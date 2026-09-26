// 상품명·상품코드 검색 및 페이지당 표시 개수 선택 UI

// 목록 API 연결용 검색어 및 페이지 크기 입력 UI
function ProductSearch() {
  return (
    <div className="product-search" role="search">
      <label className="sr-only" htmlFor="product-keyword">상품 검색</label>
      <div className="product-search__input-wrap">
        <input id="product-keyword" type="search" placeholder="상품명, 상품코드로 검색해 주세요." />
        <span aria-hidden="true">⌕</span>
      </div>
      <label className="sr-only" htmlFor="product-page-size">페이지당 상품 수</label>
      <select id="product-page-size" defaultValue="10">
        <option value="10">10건씩 보기</option>
        <option value="20">20건씩 보기</option>
        <option value="50">50건씩 보기</option>
      </select>
    </div>
  )
}

export default ProductSearch
