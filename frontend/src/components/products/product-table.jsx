// 상품 API 연결 전 목록 화면 확인용 예시 상품 행

const SAMPLE_PRODUCTS = [ // 실제 상품 API 연결 전 레이아웃 확인에만 사용하는 예시 데이터
  { id: 10, visible: 'Y', order: 10, category: '교육', name: '기초 상품관리 과정', code: 'PM20260010', price: 120000, createdAt: '2026.09.26 10:30', updatedAt: '2026.09.26 10:30' },
  { id: 9, visible: 'Y', order: 9, category: '교육', name: '실무 데이터 과정', code: 'PM20260009', price: 180000, createdAt: '2026.09.25 14:20', updatedAt: '2026.09.26 09:10' },
  { id: 8, visible: 'N', order: 8, category: '도구', name: '협업 도구 라이선스', code: 'PM20260008', price: 49000, createdAt: '2026.09.24 16:45', updatedAt: '2026.09.24 16:45' },
  { id: 7, visible: 'Y', order: 7, category: '컨설팅', name: '상품 운영 컨설팅', code: 'PM20260007', price: 350000, createdAt: '2026.09.23 11:00', updatedAt: '2026.09.25 13:15' },
  { id: 6, visible: 'Y', order: 6, category: '교육', name: '관리자 입문 과정', code: 'PM20260006', price: 90000, createdAt: '2026.09.22 15:30', updatedAt: '2026.09.22 15:30' },
  { id: 5, visible: 'Y', order: 5, category: '도구', name: '재고 관리 템플릿', code: 'PM20260005', price: 25000, createdAt: '2026.09.21 09:40', updatedAt: '2026.09.23 10:20' },
  { id: 4, visible: 'N', order: 4, category: '교육', name: '판매 분석 심화 과정', code: 'PM20260004', price: 220000, createdAt: '2026.09.20 17:10', updatedAt: '2026.09.20 17:10' },
  { id: 3, visible: 'Y', order: 3, category: '컨설팅', name: '초기 상품 진단', code: 'PM20260003', price: 200000, createdAt: '2026.09.19 13:25', updatedAt: '2026.09.21 11:05' },
  { id: 2, visible: 'Y', order: 2, category: '도구', name: '상품 등록 가이드', code: 'PM20260002', price: 19000, createdAt: '2026.09.18 08:50', updatedAt: '2026.09.18 08:50' },
  { id: 1, visible: 'Y', order: 1, category: '교육', name: '상품관리 시작하기', code: 'PM20260001', price: 70000, createdAt: '2026.09.17 12:00', updatedAt: '2026.09.17 12:00' },
]

// 상품 노출·분류·가격·등록 및 수정 정보 표
function ProductTable() {
  return (
    <div className="product-table-wrap">
      <table className="product-table">
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
          {SAMPLE_PRODUCTS.map((product) => (
            <tr key={product.id}>
              <td>{product.id}</td>
              <td><span className={'visibility-badge visibility-badge--' + product.visible.toLowerCase()}>{product.visible}</span></td>
              <td>{product.order}</td>
              <td>{product.category}</td>
              <td className="product-name">{product.name}</td>
              <td>{product.code}</td>
              <td>{product.price.toLocaleString('ko-KR')}원</td>
              <td>{product.createdAt}</td>
              <td>{product.updatedAt}</td>
              <td><button className="table-action" type="button">수정</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default ProductTable
