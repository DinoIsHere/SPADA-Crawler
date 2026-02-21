document.addEventListener('DOMContentLoaded', async () => {
    const dashboardContent = document.getElementById('dashboard-content');
    dashboardContent.innerHTML = 'Loading dashboard data...';

    try {
        const response = await fetch('/data');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const result = await response.json();
        const allCourseData = result.data;

        if (allCourseData.length === 0) {
            dashboardContent.innerHTML = '<p>No course data available yet.</p>';
            return;
        }

        dashboardContent.innerHTML = ''; // Clear loading message

        allCourseData.forEach(course => {
            const courseDiv = document.createElement('div');
            courseDiv.className = 'course-card';
            courseDiv.innerHTML = `
                <h2>${course.course_title}</h2>
                <h3>Assignments:</h3>
                <ul>
                    ${course.assignments.map(assign => `<li><a href="${assign.url}" target="_blank">${assign.text}</a></li>`).join('')}
                    ${course.assignments.length === 0 ? '<li>No assignments found.</li>' : ''}
                </ul>
                <h3>Attendance:</h3>
                <ul>
                    ${course.attendance.map(attend => `<li><a href="${attend.url}" target="_blank">${attend.text}</a></li>`).join('')}
                    ${course.attendance.length === 0 ? '<li>No attendance records found.</li>' : ''}
                </ul>
            `;
            dashboardContent.appendChild(courseDiv);
        });

    } catch (error) {
        console.error('Error fetching dashboard data:', error);
        dashboardContent.innerHTML = `<p>Error loading data: ${error.message}</p>`;
    }
});