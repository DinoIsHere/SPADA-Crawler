document.addEventListener('DOMContentLoaded', async () => {
    const dashboardContent = document.getElementById('dashboard-content');
    const prioritySection = document.getElementById('priority-section');
    const priorityGrid = document.getElementById('priority-grid');
    const searchInput = document.getElementById('course-search');
    const refreshBtn = document.getElementById('refresh-btn');
    const trayClock = document.getElementById('tray-clock');

    // Stats elements
    const statTotalCourses = document.getElementById('stat-total-courses');
    const statPendingTasks = document.getElementById('stat-pending-tasks');
    const statLastUpdate = document.getElementById('stat-last-update');

    let allCourseData = [];
    let taskStatus = {};

    // --- Win98 Navigation Logic ---
    const toolBtns = document.querySelectorAll('.tool-btn');
    const sections = document.querySelectorAll('.content-section');

    toolBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const target = btn.id.replace('nav-', '');

            toolBtns.forEach(b => b.classList.remove('active-win'));
            btn.classList.add('active-win');

            sections.forEach(section => {
                section.classList.remove('active');
                if (section.id === `${target}-section`) {
                    section.classList.add('active');
                }
            });
        });
    });

    // --- Live Clock ---
    function updateClock() {
        const now = new Date();
        trayClock.textContent = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    setInterval(updateClock, 1000);
    updateClock();

    // --- Data Logic ---
    async function fetchData() {
        dashboardContent.innerHTML = '<div class="loading-state"><p>Accessing remote database...</p></div>';

        try {
            const response = await fetch('/data');
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const result = await response.json();
            allCourseData = result.data;
            taskStatus = result.status || {};

            updateStats();
            renderPriorityTasks(allCourseData);
            renderDashboard(allCourseData);
            renderSettingsList(allCourseData);
            renderAICourseScope(allCourseData);
            loadAIConfig();
            statLastUpdate.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

        } catch (error) {
            console.error('Error fetching dashboard data:', error);
            dashboardContent.innerHTML = `<p style="padding: 20px;">System Error: ${error.message}</p>`;
        }
    }

    function updateStats() {
        statTotalCourses.textContent = allCourseData.length;
        let pendingCount = 0;
        allCourseData.forEach(course => {
            if (course.assignments) {
                course.assignments.forEach(task => {
                    if (!taskStatus[task.url]) pendingCount++;
                });
            }
        });
        statPendingTasks.textContent = pendingCount;
    }

    async function toggleTaskStatus(url, completed) {
        taskStatus[url] = completed;
        updateStats();

        try {
            await fetch('/toggle-task', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, completed })
            });
        } catch (error) {
            console.error('Error toggling task:', error);
        }
    }

    window.handleToggle = (url, completed) => {
        toggleTaskStatus(url, completed);
        renderDashboard(allCourseData);
        renderPriorityTasks(allCourseData);
    };

    function renderPriorityTasks(courses) {
        const priorityKeywords = ['kuis', 'uts', 'uas', 'ujian', 'test'];
        const priorityTasks = [];

        courses.forEach(course => {
            if (course.assignments) {
                course.assignments.forEach(task => {
                    if (taskStatus[task.url]) return;
                    const isPriority = priorityKeywords.some(kw => task.text.toLowerCase().includes(kw));
                    if (isPriority) {
                        priorityTasks.push({ ...task, courseTitle: course.course_title });
                    }
                });
            }
        });

        if (priorityTasks.length > 0) {
            prioritySection.style.display = 'block';
            priorityGrid.innerHTML = priorityTasks.slice(0, 3).map(task => `
                <div class="priority-card">
                    <div style="display: flex; justify-content: space-between;">
                        <span class="win-badge">! PRIORITY</span>
                        <button class="win-btn" onclick="window.handleToggle('${task.url}', true)" style="font-size: 9px;">Dismiss</button>
                    </div>
                    <div style="font-weight: bold;">${task.text}</div>
                    <div style="font-size: 10px; color: #555;">${task.courseTitle}</div>
                    ${task.due_date ? `<div style="color: red; font-size: 10px;">Due: ${task.due_date}</div>` : ''}
                    <a href="${task.url}" target="_blank" style="margin-top: 5px;">[Open File]</a>
                </div>
            `).join('');
        } else {
            prioritySection.style.display = 'none';
        }
    }

    function renderDashboard(courses) {
        if (courses.length === 0) {
            dashboardContent.innerHTML = '<p>No programs found.</p>';
            return;
        }

        dashboardContent.innerHTML = '';
        courses.forEach(course => {
            const courseDiv = document.createElement('div');
            courseDiv.className = 'win-course-item';

            const assignmentsHtml = (course.assignments && course.assignments.length > 0)
                ? course.assignments.map(assign => renderTaskItem(assign, 'assignment')).join('')
                : '';

            const attendanceHtml = (course.attendance && course.attendance.length > 0)
                ? course.attendance.map(attend => renderTaskItem(attend, 'attendance')).join('')
                : '';

            const quizzesHtml = (course.quizzes && course.quizzes.length > 0)
                ? course.quizzes.map(quiz => renderTaskItem(quiz, 'quiz')).join('')
                : '';

            courseDiv.innerHTML = `
                <div class="win-course-title">
                    <img src="https://win98icons.alexmeub.com/icons/png/directory_open_file_mydocs-4.png" width="16">
                    ${course.course_title}
                </div>
                <div style="padding-left: 20px;">
                    ${assignmentsHtml}
                    ${attendanceHtml}
                    ${quizzesHtml}
                    ${!assignmentsHtml && !attendanceHtml && !quizzesHtml ? '<div style="font-size: 10px; font-style: italic;">(No resources found)</div>' : ''}
                </div>
            `;
            dashboardContent.appendChild(courseDiv);
        });
    }

    function renderTaskItem(task, type) {
        const isDone = taskStatus[task.url] === true;
        let autoBtn = '';

        if (type === 'attendance') {
            autoBtn = `<button class="win-btn auto-btn" onclick="window.runAuto('attendance', '${task.url}')">Auto-Check</button>`;
        } else if (type === 'quiz') {
            const isTarget = /quiz|post test|pre test/i.test(task.text);
            if (isTarget) {
                autoBtn = `<button class="win-btn auto-btn" onclick="window.runAuto('quiz', '${task.url}')">AI Solve</button>`;
            }
        }

        return `
            <div style="display: flex; align-items: flex-start; gap: 8px; margin-bottom: 8px; ${isDone ? 'color: #888;' : ''}">
                <input type="checkbox" class="win-check" ${isDone ? 'checked' : ''} onchange="window.handleToggle('${task.url}', this.checked)">
                <div style="flex-grow: 1;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <a href="${task.url}" target="_blank" style="text-decoration: ${isDone ? 'line-through' : 'none'}; color: ${isDone ? '#888' : 'blue'};">
                            [${type.toUpperCase()}] ${task.text}
                        </a>
                        ${!isDone ? autoBtn : ''}
                    </div>
                    ${task.due_date ? `<div style="font-size: 10px;">Due: ${task.due_date}</div>` : ''}
                </div>
            </div>
        `;
    }

    window.runAuto = async (type, url) => {
        const aiStatus = document.getElementById('ai-status');
        aiStatus.textContent = `AI Engine: Running ${type} automation...`;
        aiStatus.style.color = 'blue';

        try {
            const endpoint = type === 'attendance' ? '/run-attendance' : '/run-quiz';
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });
            const result = await response.json();

            if (result.success) {
                aiStatus.textContent = `AI Engine: ${type} successful!`;
                aiStatus.style.color = 'green';
                window.handleToggle(url, true);
            } else {
                aiStatus.textContent = `AI Engine: ${type} failed.`;
                aiStatus.style.color = 'red';
            }
        } catch (error) {
            console.error('Automation error:', error);
            aiStatus.textContent = `AI Engine: Error!`;
            aiStatus.style.color = 'red';
        }
    };

    function renderSettingsList(courses) {
        const settingsList = document.getElementById('settings-course-list');
        if (!settingsList) return;

        settingsList.innerHTML = courses.map(course => `
            <div class="filter-item">
                <input type="checkbox" checked>
                <span>${course.course_title}</span>
            </div>
        `).join('');
    }

    searchInput.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase();
        const filteredCourses = allCourseData.filter(course =>
            course.course_title.toLowerCase().includes(searchTerm)
        );
        renderDashboard(filteredCourses);
    });

    refreshBtn.addEventListener('click', fetchData);
    fetchData();

    // --- Interactive Toy Logic ---
    const atomToy = document.getElementById('atom-toy');
    const atomContainer = atomToy.querySelector('.atom');

    atomContainer.addEventListener('click', () => {
        atomContainer.classList.add('boosted');
        setTimeout(() => atomContainer.classList.remove('boosted'), 3000);
    });

    // --- Classic Draggable Windows ---
    function makeDraggable(el) {
        let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
        const titleBar = el.querySelector('.title-bar');

        if (titleBar) {
            titleBar.onmousedown = dragMouseDown;
        }

        function dragMouseDown(e) {
            e = e || window.event;
            pos3 = e.clientX;
            pos4 = e.clientY;
            document.onmouseup = closeDragElement;
            document.onmousemove = elementDrag;

            // Bring to front
            document.querySelectorAll('.window').forEach(w => w.style.zIndex = 100);
            el.style.zIndex = 1000;
        }

        function elementDrag(e) {
            e = e || window.event;
            pos1 = pos3 - e.clientX;
            pos2 = pos4 - e.clientY;
            pos3 = e.clientX;
            pos4 = e.clientY;
            el.style.top = (el.offsetTop - pos2) + "px";
            el.style.left = (el.offsetLeft - pos1) + "px";
        }

        function closeDragElement() {
            document.onmouseup = null;
            document.onmousemove = null;
        }
    }

    makeDraggable(document.getElementById('main-explorer'));
    makeDraggable(document.getElementById('atom-toy'));
    // --- AI Configuration Logic ---
    let aiConfig = { ai_model: 'gemini-1.5-flash', auto_courses: {} };

    async function loadAIConfig() {
        try {
            const response = await fetch('/ai-config');
            aiConfig = await response.json();
            document.getElementById('ai-model-select').value = aiConfig.ai_model;
            renderAICourseScope(allCourseData);
        } catch (error) {
            console.error('Error loading AI config:', error);
        }
    }

    async function saveAIConfig() {
        const model = document.getElementById('ai-model-select').value;
        const apiKey = document.getElementById('ai-api-key').value;

        if (apiKey) aiConfig.gemini_api_key = apiKey;
        aiConfig.ai_model = model;

        try {
            const response = await fetch('/ai-config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(aiConfig)
            });
            if (response.ok) {
                alert('AI Configuration Saved!');
                document.getElementById('ai-api-key').value = '';
            }
        } catch (error) {
            console.error('Error saving AI config:', error);
        }
    }

    function renderAICourseScope(courses) {
        const scopeContainer = document.getElementById('ai-course-scope');
        if (!scopeContainer) return;

        scopeContainer.innerHTML = courses.map(course => {
            const courseSettings = aiConfig.auto_courses[course.course_title] || { attendance: false, quiz: false };
            return `<div class="filter-item" style="flex-direction: column; align-items: flex-start; border-bottom: 1px dotted #ccc; padding: 10px 0;">
                    <div style="font-weight: bold; font-size: 10px; margin-bottom: 5px;">${course.course_title}</div>
                    <div style="display: flex; gap: 15px; padding-left: 10px;">
                        <label style="font-size: 9px; display: flex; align-items: center; gap: 4px;">
                            <input type="checkbox" ${courseSettings.attendance ? 'checked' : ''} onchange="window.updateCourseAI('${course.course_title}', 'attendance', this.checked)"> 
                            Auto-Attendance
                        </label>
                        <label style="font-size: 9px; display: flex; align-items: center; gap: 4px;">
                            <input type="checkbox" ${courseSettings.quiz ? 'checked' : ''} onchange="window.updateCourseAI('${course.course_title}', 'quiz', this.checked)"> 
                            Auto-Quiz
                        </label>
                    </div>
                </div>`;
        }).join('');
    }

    window.updateCourseAI = (courseTitle, type, enabled) => {
        if (!aiConfig.auto_courses[courseTitle]) aiConfig.auto_courses[courseTitle] = { attendance: false, quiz: false };
        aiConfig.auto_courses[courseTitle][type] = enabled;
    };

    document.getElementById('save-ai-config')?.addEventListener('click', saveAIConfig);

    document.getElementById('run-all-auto')?.addEventListener('click', async () => {
        const status = document.getElementById('ai-status');
        status.textContent = "AI Engine: Initializing collective run...";
        status.style.color = "blue";

        try {
            const response = await fetch('/run-collective-automation', { method: 'POST' });
            const result = await response.json();
            status.textContent = `AI Engine: Completed. ${result.results?.length || 0} tasks processed.`;
            status.style.color = "green";
            fetchData();
        } catch (error) {
            status.textContent = "AI Engine: Error in collective run.";
            status.style.color = "red";
        }
    });
});
