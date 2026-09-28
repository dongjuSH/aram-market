const dateTimeFormatter = new Intl.DateTimeFormat('ko-KR', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hourCycle: 'h23',
  timeZone: 'Asia/Seoul',
})

// ISO 시각을 관리자 목록용 한국 날짜·시각 두 줄 표기로 변환
function formatDateTime(value) {
  if (!value) return null

  const parts = Object.fromEntries(
    dateTimeFormatter
      .formatToParts(new Date(value))
      .filter(({ type }) => type !== 'literal')
      .map(({ type, value: partValue }) => [type, partValue]),
  )

  return {
    date: `${parts.year}. ${parts.month}. ${parts.day}.`,
    time: `${parts.hour}:${parts.minute}:${parts.second}`,
  }
}

function DateTimeCell({ value }) {
  const dateTime = formatDateTime(value)

  if (!dateTime) return <td className="product-date-time">-</td>

  return (
    <td className="product-date-time">
      <span>{dateTime.date}</span>
      <span>{dateTime.time}</span>
    </td>
  )
}

// 상품 노출·분류·가격·등록 및 수정 정보 표
function ProductTable({ products, page, pageSize, isLoading, status, restoringId, onEdit, onRestore }) {
  return (
    <div className="product-table-wrap">
      <table className="product-table">
        <colgroup>
          <col className="product-table__col--number" />
          <col className="product-table__col--visibility" />
          <col className="product-table__col--order" />
          <col className="product-table__col--category" />
          <col className="product-table__col--name" />
          <col className="product-table__col--code" />
          <col className="product-table__col--price" />
          <col className="product-table__col--date" />
          <col className="product-table__col--date" />
          <col className="product-table__col--manage" />
        </colgroup>
        <thead>
          <tr>
            <th>번호</th>
            <th>노출여부</th>
            <th>노출순서</th>
            <th>카테고리</th>
            <th>상품명</th>
            <th>상품코드</th>
            <th>가격</th>
            <th>등록일</th>
            <th>수정일</th>
            <th>관리</th>
          </tr>
        </thead>
        <tbody>
          {!isLoading && products.map((product, index) => (
            <tr key={product.id}>
              <td>{((page - 1) * pageSize) + index + 1}</td>
              <td><span className={'visibility-badge visibility-badge--' + (product.visible ? 'y' : 'n')}>{product.visible ? 'Y' : 'N'}</span></td>
              <td>{product.display_order}</td>
              <td>{product.category}</td>
              <td className="product-name">{product.name}</td>
              <td>{product.code}</td>
              <td>{product.price.toLocaleString('ko-KR')}원</td>
              <DateTimeCell value={product.created_at} />
              <DateTimeCell value={product.updated_at} />
              <td>
                {status === 'deleted' ? (
                  <button
                    className="table-action table-action--restore"
                    type="button"
                    disabled={restoringId === product.id}
                    onClick={() => onRestore(product)}
                  >
                    {restoringId === product.id ? '복원 중' : '복원'}
                  </button>
                ) : (
                  <button className="table-action" type="button" onClick={() => onEdit(product.id)}>수정</button>
                )}
              </td>
            </tr>
          ))}
          {isLoading && (
            <tr><td className="product-table__message" colSpan="10"><span>상품을 불러오고 있습니다.</span></td></tr>
          )}
          {!isLoading && products.length === 0 && (
            <tr><td className="product-table__message" colSpan="10"><span>{status === 'deleted' ? '삭제된 상품이 없습니다.' : '등록된 상품이 없습니다.'}</span></td></tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

export default ProductTable
