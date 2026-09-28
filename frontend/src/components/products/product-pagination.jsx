// 상품 목록 하단 페이지 이동 및 등록 버튼 UI

// 현재 페이지 주변 번호 계산
function getPageNumbers(currentPage, totalPages) {
  const start = Math.max(1, Math.min(currentPage - 2, totalPages - 4))
  const end = Math.min(totalPages, start + 4)
  return Array.from({ length: Math.max(0, end - start + 1) }, (_, index) => start + index)
}

// 페이지 이동과 상품 등록 화면 이동 UI
function ProductPagination({ page, total, pageSize, onPageChange, onCreate }) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const pageNumbers = getPageNumbers(page, totalPages)
  return (
    <div className="product-footer">
      <nav className="pagination" aria-label="상품 목록 페이지">
        <button type="button" aria-label="이전 페이지" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>‹</button>
        {pageNumbers.map((pageNumber) => (
          <button
            key={pageNumber}
            className={pageNumber === page ? 'is-current' : ''}
            type="button"
            aria-current={pageNumber === page ? 'page' : undefined}
            onClick={() => onPageChange(pageNumber)}
          >
            {pageNumber}
          </button>
        ))}
        <button type="button" aria-label="다음 페이지" disabled={page >= totalPages} onClick={() => onPageChange(page + 1)}>›</button>
      </nav>
      {onCreate && <button className="product-create" type="button" onClick={onCreate}><span aria-hidden="true">＋</span> 상품 등록</button>}
    </div>
  )
}

export default ProductPagination
