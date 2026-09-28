// 상품명·상품코드 검색 및 페이지당 표시 개수 선택 UI

// 상품명·상품코드 검색어와 페이지 크기를 상위 목록 상태에 전달
function ProductSearch({ keyword, pageSize, onKeywordChange, onSearch, onPageSizeChange }) {
  return (
    <form className="product-search" role="search" onSubmit={onSearch}>
      <label className="sr-only" htmlFor="product-keyword">상품 검색</label>
      <div className="product-search__input-wrap">
        <input
          id="product-keyword"
          type="search"
          value={keyword}
          onChange={(event) => onKeywordChange(event.target.value)}
          placeholder="상품명, 상품코드로 검색해 주세요."
        />
        <button type="submit" aria-label="검색">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="11" cy="11" r="6.5" />
            <path d="m16 16 4 4" />
          </svg>
        </button>
      </div>
      <label className="sr-only" htmlFor="product-page-size">페이지당 상품 수</label>
      <div className="product-search__select-wrap">
        <select id="product-page-size" value={pageSize} onChange={(event) => onPageSizeChange(Number(event.target.value))}>
          <option value="10">10건씩 보기</option>
          <option value="50">50건씩 보기</option>
          <option value="100">100건씩 보기</option>
        </select>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m7 10 5 5 5-5" /></svg>
      </div>
    </form>
  )
}

export default ProductSearch
