import { Link } from 'react-router-dom';

const NotFound = () => {
  return (
    <section className="flex min-h-[60vh] flex-col items-center justify-center gap-4 text-center">
      <div>
        <p className="text-sm font-semibold text-slate-500">404</p>
        <h1 className="mt-2 text-3xl font-bold text-slate-900">页面未找到</h1>
        <p className="mt-2 text-slate-600">请检查链接或返回控制台首页。</p>
      </div>
      <Link
        to="/"
        className="inline-flex items-center rounded-md bg-primary px-4 py-2 font-medium text-white"
      >
        返回 Dashboard
      </Link>
    </section>
  );
};

export default NotFound;
