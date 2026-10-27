/**
 * Utility functions for Reports module
 */

export const formatDateLocal = (date) => {
    const yyyy = date.getFullYear();
    const mm = String(date.getMonth() + 1).padStart(2, '0');
    const dd = String(date.getDate()).padStart(2, '0');
    return `${yyyy}-${mm}-${dd}`;
};

export const formatDateDisplay = (dateStr) => {
    if (!dateStr) return '';
    const parts = dateStr.trim().split(' ');
    const datePart = parts[0];
    let timePart = parts.length > 1 ? parts[1] : '';
    if (timePart) {
        const cleanTime = timePart.split('.')[0];
        timePart = cleanTime.length === 5 ? `${cleanTime}:00` : cleanTime.slice(0, 8);
    }
    const dSub = datePart.split('-');
    if (dSub.length === 3) {
        const formattedDate = `${dSub[2]}/${dSub[1]}/${dSub[0]}`;
        return (timePart && timePart !== '23:59:59') ? `${formattedDate} ${timePart}` : formattedDate;
    }
    if (parts.length > 1) return `${datePart} ${timePart}`;
    if (datePart.split('/').length === 3) return `${datePart} 00:00:00`;
    return dateStr;
};

export const parseReportDate = (dStr) => {
    if (!dStr || dStr === '-') return null;
    const datePart = dStr.split(' ')[0].trim();
    if (datePart.includes('/')) {
        const parts = datePart.split('/');
        if (parts.length === 3) {
            return new Date(`${parts[2]}-${parts[1].padStart(2, '0')}-${parts[0].padStart(2, '0')}T23:59:59`);
        }
    } else if (datePart.includes('-')) {
        const parts = datePart.split('-');
        if (parts.length === 3) {
            return new Date(`${parts[0]}-${parts[1].padStart(2, '0')}-${parts[2].padStart(2, '0')}T23:59:59`);
        }
    }
    const d = new Date(datePart);
    return isNaN(d.getTime()) ? null : d;
};

export const checkIsStale = (lastUpdate, dateEnd) => {
    if (!dateEnd || !lastUpdate || lastUpdate === '-') return false;
    const exDate = parseReportDate(lastUpdate);
    const targetDate = parseReportDate(dateEnd);
    if (exDate && targetDate) {
        return exDate < targetDate;
    }
    return false;
};

export const computeStaleExchanges = (exchanges, selectedExchanges, dateEnd) => {
    if (!dateEnd) return [];
    const targetDate = parseReportDate(dateEnd);
    if (!targetDate) return [];
    const stale = [];

    exchanges.forEach(ex => {
        if (!selectedExchanges.includes(ex.name)) return;
        if (ex.lastUpdate === '-' || !ex.lastUpdate) return;
        const exDate = parseReportDate(ex.lastUpdate);
        if (exDate && exDate < targetDate) {
            stale.push({
                name: ex.name,
                lastUpdate: ex.lastUpdate.split(' ')[0]
            });
        }
    });
    return stale;
};
