import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Card, Button, Badge } from '../components/Core';

export const Dashboard: React.FC = () => {
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState<'overview' | 'lms' | 'chat'>('overview');

  if (!user) return null;

  const role = user.roles[0] || 'Student';

  return (
    <div className="min-h-screen bg-[#0b0f19] flex">
      {/* Sidebar */}
      <aside className="w-64 bg-[#111827]/60 border-r border-slate-800/80 p-6 flex flex-col justify-between">
        <div>
          <div className="flex items-center space-x-3 mb-8">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white shadow-md shadow-indigo-900/50">
              N
            </div>
            <span className="text-xl font-bold bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
              Nexora AI
            </span>
          </div>

          <div className="space-y-2">
            <button
              onClick={() => setActiveTab('overview')}
              className={`w-full flex items-center space-x-3 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                activeTab === 'overview' ? 'bg-indigo-600/10 text-indigo-400' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/30'
              }`}
            >
              <span>Dashboard</span>
            </button>
            <button
              onClick={() => setActiveTab('lms')}
              className={`w-full flex items-center space-x-3 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                activeTab === 'lms' ? 'bg-indigo-600/10 text-indigo-400' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/30'
              }`}
            >
              <span>LMS Study Hub</span>
            </button>
            <button
              onClick={() => setActiveTab('chat')}
              className={`w-full flex items-center space-x-3 px-4 py-2.5 rounded-lg text-sm font-semibold transition-all ${
                activeTab === 'chat' ? 'bg-indigo-600/10 text-indigo-400' : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/30'
              }`}
            >
              <span>Real-Time Chat</span>
            </button>
          </div>
        </div>

        <div className="border-t border-slate-800/80 pt-6">
          <div className="flex items-center space-x-3 mb-4">
            <div className="w-10 h-10 rounded-full bg-slate-800 border border-slate-700/80 flex items-center justify-center font-bold text-slate-300">
              {user.first_name[0]}{user.last_name[0]}
            </div>
            <div>
              <p className="text-sm font-bold text-slate-100">{user.first_name} {user.last_name}</p>
              <p className="text-xs text-slate-500">{role}</p>
            </div>
          </div>
          <Button variant="ghost" size="sm" onClick={logout} className="w-full justify-start text-red-400 hover:text-red-300 hover:bg-red-950/20">
            Sign Out
          </Button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 p-8 overflow-y-auto max-h-screen">
        <header className="flex justify-between items-center mb-8">
          <div>
            <h2 className="text-2xl font-bold text-slate-100">Welcome Back, {user.first_name}!</h2>
            <p className="text-slate-400 text-sm">Here is a summary of your workspace today.</p>
          </div>
          <Badge variant="info">Subdomain Context: {user.roles.includes('Admin') ? 'Org Admin' : 'Academic Member'}</Badge>
        </header>

        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* Stat Cards Row */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <Card hoverable>
                <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Attendance Rate</p>
                <div className="flex items-baseline space-x-2 mt-2">
                  <span className="text-3xl font-extrabold text-slate-100">92.4%</span>
                  <span className="text-xs text-emerald-400 font-semibold">▲ 1.2% this week</span>
                </div>
                <div className="w-full bg-slate-800 h-1.5 rounded-full mt-4 overflow-hidden">
                  <div className="bg-indigo-500 h-full rounded-full" style={{ width: '92.4%' }} />
                </div>
              </Card>
              
              <Card hoverable>
                <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Pending Assignments</p>
                <div className="flex items-baseline space-x-2 mt-2">
                  <span className="text-3xl font-extrabold text-slate-100">3</span>
                  <span className="text-xs text-slate-500">Next due in 2 days</span>
                </div>
                <div className="flex space-x-1.5 mt-4">
                  <Badge variant="danger">High Priority</Badge>
                  <Badge variant="neutral">CS101</Badge>
                </div>
              </Card>

              <Card hoverable>
                <p className="text-slate-400 text-xs font-semibold uppercase tracking-wider">Academic Grade (GPA)</p>
                <div className="flex items-baseline space-x-2 mt-2">
                  <span className="text-3xl font-extrabold text-slate-100">3.85 / 4.0</span>
                  <span className="text-xs text-indigo-400 font-semibold">Top 5% of Batch</span>
                </div>
                <div className="w-full bg-slate-800 h-1.5 rounded-full mt-4 overflow-hidden">
                  <div className="bg-gradient-to-r from-blue-500 to-indigo-500 h-full rounded-full" style={{ width: '96.2%' }} />
                </div>
              </Card>
            </div>

            {/* Dashboard Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <h3 className="text-base font-bold text-slate-100 mb-4">Today's Class Timetable</h3>
                <div className="space-y-3">
                  <div className="flex items-center justify-between p-3 bg-slate-800/30 border border-slate-800 rounded-lg">
                    <div>
                      <p className="text-sm font-semibold text-slate-200">Python Programming (CS101)</p>
                      <p className="text-xs text-slate-500">09:00 AM - 10:30 AM | Room 402</p>
                    </div>
                    <Badge variant="success">Completed</Badge>
                  </div>
                  <div className="flex items-center justify-between p-3 bg-slate-800/30 border border-slate-800 rounded-lg">
                    <div>
                      <p className="text-sm font-semibold text-slate-200">Database Systems (CS204)</p>
                      <p className="text-xs text-slate-500">11:00 AM - 12:30 PM | Lab 2</p>
                    </div>
                    <Badge variant="info">Active Now</Badge>
                  </div>
                  <div className="flex items-center justify-between p-3 bg-slate-800/30 border border-slate-800 rounded-lg opacity-60">
                    <div>
                      <p className="text-sm font-semibold text-slate-200">Machine Learning Basics (CS302)</p>
                      <p className="text-xs text-slate-500">02:00 PM - 03:30 PM | Room 101</p>
                    </div>
                    <Badge variant="neutral">Scheduled</Badge>
                  </div>
                </div>
              </Card>

              <Card>
                <h3 className="text-base font-bold text-slate-100 mb-4">AI Study Insights & Recommendations</h3>
                <div className="space-y-4">
                  <div className="p-3 bg-indigo-950/20 border border-indigo-900/30 rounded-lg">
                    <p className="text-xs font-bold text-indigo-400 uppercase tracking-wider mb-1">Study Advice</p>
                    <p className="text-xs text-slate-300">
                      Based on your recent scores, you could improve by practicing more recursion in Python. We recommend checking out the "Python Advanced" notes uploaded by Prof. John.
                    </p>
                  </div>
                  <div className="p-3 bg-rose-950/20 border border-rose-900/30 rounded-lg">
                    <p className="text-xs font-bold text-rose-400 uppercase tracking-wider mb-1">Attendance Alert</p>
                    <p className="text-xs text-slate-300">
                      Your attendance in "Database Systems" is approaching the minimum requirement (78%). Make sure to join the next lecture.
                    </p>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        )}

        {activeTab === 'lms' && (
          <div className="space-y-6">
            <Card>
              <h3 className="text-lg font-bold text-slate-100 mb-4">LMS Study Hub</h3>
              <p className="text-slate-400 text-sm mb-6">
                Access your assignments, uploaded class notes, slides, and study guides.
              </p>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">Class Notes & Materials</h4>
                  <div className="p-4 bg-slate-800/30 border border-slate-800 rounded-lg hover:border-slate-700 transition-all cursor-pointer">
                    <p className="text-sm font-semibold text-slate-200">CS101_Lecture_01.pdf</p>
                    <p className="text-xs text-slate-500 mt-1">Uploaded by Teacher | PDF Document | 4.2 MB</p>
                  </div>
                  <div className="p-4 bg-slate-800/30 border border-slate-800 rounded-lg hover:border-slate-700 transition-all cursor-pointer">
                    <p className="text-sm font-semibold text-slate-200">CS204_Relational_Algebra.pptx</p>
                    <p className="text-xs text-slate-500 mt-1">Uploaded by Teacher | PowerPoint | 12.8 MB</p>
                  </div>
                </div>

                <div className="space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">Active Assignments</h4>
                  <div className="p-4 bg-slate-800/30 border border-slate-800 rounded-lg">
                    <div className="flex justify-between items-start">
                      <div>
                        <p className="text-sm font-semibold text-slate-200">Variables & Lists HW</p>
                        <p className="text-xs text-slate-500 mt-1">Deadline: June 30, 2026</p>
                      </div>
                      <Badge variant="danger">Pending</Badge>
                    </div>
                  </div>
                  <div className="p-4 bg-slate-800/30 border border-slate-800 rounded-lg opacity-65">
                    <div className="flex justify-between items-start">
                      <div>
                        <p className="text-sm font-semibold text-slate-200">Relational Algebra HW 1</p>
                        <p className="text-xs text-slate-500 mt-1">Graded: A+</p>
                      </div>
                      <Badge variant="success">Submitted</Badge>
                    </div>
                  </div>
                </div>
              </div>
            </Card>
          </div>
        )}

        {activeTab === 'chat' && (
          <div className="h-[75vh] flex">
            <Card className="flex-1 flex overflow-hidden p-0">
              {/* Rooms Sidebar */}
              <div className="w-1/3 border-r border-slate-800/80 flex flex-col">
                <div className="p-4 border-b border-slate-800/80">
                  <input
                    type="text"
                    placeholder="Search messages..."
                    className="w-full bg-slate-800/40 border border-slate-700/80 rounded-lg px-3 py-1.5 text-xs text-slate-200"
                  />
                </div>
                <div className="flex-1 overflow-y-auto divide-y divide-slate-800/40">
                  <div className="p-4 bg-slate-850 hover:bg-slate-800/20 cursor-pointer flex items-center space-x-3">
                    <div className="w-8 h-8 rounded-full bg-indigo-950 flex items-center justify-center font-bold text-indigo-400 text-xs">
                      T
                    </div>
                    <div className="flex-1">
                      <div className="flex justify-between">
                        <span className="text-xs font-bold text-slate-200">Prof. Sarah (Teacher)</span>
                        <span className="text-[10px] text-slate-500">12:30 PM</span>
                      </div>
                      <p className="text-[11px] text-slate-400 truncate mt-0.5">Please review the syllabus slides.</p>
                    </div>
                  </div>
                  <div className="p-4 hover:bg-slate-800/20 cursor-pointer flex items-center space-x-3">
                    <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center font-bold text-slate-400 text-xs">
                      B
                    </div>
                    <div className="flex-1">
                      <div className="flex justify-between">
                        <span className="text-xs font-bold text-slate-200">Class Group (Sec A)</span>
                        <span className="text-[10px] text-slate-500">Yesterday</span>
                      </div>
                      <p className="text-[11px] text-slate-400 truncate mt-0.5">Are we meeting in Lab 2 today?</p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Active Chat Pane */}
              <div className="flex-1 flex flex-col justify-between bg-slate-900/10">
                <div className="p-4 border-b border-slate-800/80 bg-slate-950/20 flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 rounded-full bg-indigo-950 flex items-center justify-center font-bold text-indigo-400 text-xs">
                      T
                    </div>
                    <div>
                      <p className="text-xs font-bold text-slate-200">Prof. Sarah (Teacher)</p>
                      <p className="text-[10px] text-emerald-400 flex items-center">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1" /> Active Now
                      </p>
                    </div>
                  </div>
                </div>
                
                <div className="flex-1 p-4 overflow-y-auto space-y-3">
                  <div className="flex justify-start">
                    <div className="max-w-[70%] bg-slate-800/50 border border-slate-800 p-3 rounded-xl rounded-tl-none">
                      <p className="text-xs text-slate-200">
                        Hello Class, make sure to read the first lecture slides before tomorrow's lecture.
                      </p>
                      <span className="text-[9px] text-slate-500 block mt-1">12:28 PM</span>
                    </div>
                  </div>
                  <div className="flex justify-end">
                    <div className="max-w-[70%] bg-indigo-650/80 p-3 rounded-xl rounded-tr-none text-white">
                      <p className="text-xs">
                        Will do, Professor! Is the homework assignment due tomorrow as well?
                      </p>
                      <span className="text-[9px] text-indigo-200 block mt-1 text-right">12:30 PM</span>
                    </div>
                  </div>
                </div>

                <div className="p-4 border-t border-slate-800/80 flex items-center space-x-3">
                  <input
                    type="text"
                    placeholder="Type your message here..."
                    className="flex-1 bg-slate-800/40 border border-slate-700/80 rounded-lg px-4 py-2 text-xs text-slate-200 focus:outline-none focus:border-indigo-500"
                  />
                  <Button size="sm">Send</Button>
                </div>
              </div>
            </Card>
          </div>
        )}
      </main>
    </div>
  );
};
