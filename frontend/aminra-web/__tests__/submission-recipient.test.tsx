import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {fireEvent,render,screen,within} from '@testing-library/react';
import Page from '@/app/submissions/page';
const {auth,replace,search}=vi.hoisted(()=>({auth:{user:{id:'business-a',tenant_id:'tenant-a',role:'business',is_owner:true},token:'synthetic-token',isAuthenticated:true,loading:false},replace:vi.fn(),search:new URLSearchParams()}));
vi.mock('@/components/UserAuthContext',()=>({useUserAuth:()=>auth}));
vi.mock('next/navigation',()=>({useRouter:()=>({replace}),useSearchParams:()=>search}));
function submission(id:string,name:string|null,email:string|null){return {id,company_name:'Doanh nghiệp thử',provider_name:name,provider_email:email,status:'submitted',notes:null,auditor_notes:null,doc_count:1,document_ids:['doc'],auditor_id:null,auditor_name:null,submitted_at:'2026-10-31T10:00:00Z',updated_at:'2026-10-31T10:00:00Z',deadline:null};}
function response(rows:ReturnType<typeof submission>[]){vi.stubGlobal('fetch',vi.fn(async(url)=>Response.json(String(url).includes('/provider/auditors')?{auditors:[]}:{submissions:rows})));}
beforeEach(()=>{auth.user.role='business';replace.mockReset();});
afterEach(()=>vi.unstubAllGlobals());
it('each sent submission identifies its own recipient organization and contact email',async()=>{
 response([submission('one','CB Một','one@example.invalid'),submission('two','CB Hai','two@example.invalid')]);render(<Page/>);
 const one=await screen.findByRole('button',{name:/CB Một/}),two=screen.getByRole('button',{name:/CB Hai/});
 expect(within(one).getByText('Tổ chức tiếp nhận')).toBeVisible();
 expect(within(one).getByText('Email liên hệ: one@example.invalid')).toBeVisible();
 expect(within(one).queryByText(/two@example.invalid/)).toBeNull();
 expect(within(two).getByText('Email liên hệ: two@example.invalid')).toBeVisible();
});
it('missing organization metadata is explicit and never presents invented contact details',async()=>{
 response([submission('missing',null,null)]);render(<Page/>);
 expect(await screen.findByText('Chưa có tên tổ chức tiếp nhận')).toBeVisible();
 expect(screen.queryByText(/^Email liên hệ:/)).toBeNull();
});
it('the receiving CB view keeps the business identity rather than labeling itself as the recipient',async()=>{
 auth.user.role='provider';response([submission('received','Tên CB không hiển thị','cb@example.invalid')]);render(<Page/>);
 fireEvent.click(await screen.findByRole('button',{name:/Doanh nghiệp thử.*1 hồ sơ/}));
 expect(screen.queryByText('Tổ chức tiếp nhận')).toBeNull();expect(screen.queryByText(/cb@example.invalid/)).toBeNull();
 expect(screen.getByRole('button',{name:/Doanh nghiệp thử.*1 tài liệu/})).toBeVisible();
});
