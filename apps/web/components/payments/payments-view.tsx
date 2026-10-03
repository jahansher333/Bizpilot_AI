"use client";

import React, { useState } from "react";
import Link from "next/link";
import { formatMoney, Payment } from "@/lib/schemas/payments";
import { useDailyPaymentTotal, usePayments } from "@/hooks/use-payments";
import { PaymentCreateModal } from "@/components/payments/payment-create-modal";
import { PaymentDetailModal } from "@/components/payments/payment-detail-modal";
import { PaymentVoidModal } from "@/components/payments/payment-void-modal";
import { PaymentCorrectModal } from "@/components/payments/payment-correct-modal";

interface PaymentsViewProps {
  orgId: string;
  userRole?: string; // "owner", "manager", "staff"
  token?: string;
  initialOrderId?: string;
  initialCustomerId?: string;
}

export function PaymentsView({
  orgId,
  userRole = "owner",
  token,
  initialOrderId,
  initialCustomerId,
}: PaymentsViewProps) {
  const [statusFilter, setStatusFilter] = useState<string | undefined>("all");
  const [channelFilter, setChannelFilter] = useState<string | undefined>("all");
  const [selectedCustomerId] = useState<string | undefined>(initialCustomerId);
  const [selectedOrderId] = useState<string | undefined>(initialOrderId);
  const [selectedPayment, setSelectedPayment] = useState<Payment | null>(null);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [isVoidOpen, setIsVoidOpen] = useState(false);
  const [isCorrectOpen, setIsCorrectOpen] = useState(false);

  const effectiveStatus = statusFilter === "all" ? undefined : statusFilter;
  const effectiveChannel = channelFilter === "all" ? undefined : channelFilter;

  const { data, isLoading, error, refetch } = usePayments(
    orgId,
    {
      status: effectiveStatus,
      channel: effectiveChannel,
      customerId: selectedCustomerId,
      orderId: selectedOrderId,
      limit: 100,
      offset: 0,
    },
    token
  );

  const todayStr = new Date().toISOString().split("T")[0];
  const { data: dailyTotalData } = useDailyPaymentTotal(orgId, todayStr, token);

  const normalizedRole = userRole.toLowerCase();
  const isOwner = normalizedRole === "owner";
  const isManager = normalizedRole === "manager";
  const isStaff = normalizedRole === "staff";

  // Permission flags:
  // - payments:create -> Owner, Manager, Staff
  // - payments:correct -> Owner, Manager
  // - payments:void -> Owner only
  const canCreate = isOwner || isManager || isStaff;
  const canCorrect = isOwner || isManager;
  const canVoid = isOwner;

  const payments = data?.items || [];

  const handleOpenDetail = (payment: Payment) => {
    setSelectedPayment(payment);
    setIsDetailOpen(true);
  };

  const handleOpenVoid = (payment: Payment) => {
    setSelectedPayment(payment);
    setIsVoidOpen(true);
  };

  const handleOpenCorrect = (payment: Payment) => {
    setSelectedPayment(payment);
    setIsCorrectOpen(true);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "active":
        return "bg-green-100 text-green-800 border-green-200";
      case "voided":
        return "bg-red-100 text-red-800 border-red-200";
      case "corrected":
        return "bg-amber-100 text-amber-800 border-amber-200";
      default:
        return "bg-gray-100 text-gray-800 border-gray-200";
    }
  };

  const formatChannel = (ch: string) => {
    switch (ch) {
      case "cash":
        return "Cash";
      case "bank_transfer":
        return "Bank Transfer";
      case "cheque":
        return "Cheque";
      case "mobile_wallet":
        return "Mobile Wallet";
      default:
        return ch;
    }
  };

  return (
    <div className="space-y-6 p-6 max-w-[1600px] mx-auto">
      {/* Title & Top Actions Header Bar */}
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-1">
          <h1 className="font-headline-lg text-2xl lg:text-3xl font-semibold tracking-tight text-on-surface">
            Payments &amp; Receipts
          </h1>
          <p className="font-body-md text-sm text-on-surface-variant max-w-3xl">
            Record money you have received (cash, bank transfer, wallet) and see today's recorded collections.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <Link
            href={`/workspace/${orgId}/orders`}
            className="inline-flex items-center gap-1.5 rounded-lg border border-outline-variant/40 bg-surface-container-lowest px-3.5 py-2 font-body-sm text-sm font-medium text-on-surface shadow-xs hover:bg-surface-container-high transition-colors"
          >
            <span className="material-symbols-outlined text-[18px] text-outline">shopping_bag</span>
            <span>Orders Directory</span>
          </Link>
          <Link
            href={`/workspace/${orgId}/customers`}
            className="inline-flex items-center gap-1.5 rounded-lg border border-outline-variant/40 bg-surface-container-lowest px-3.5 py-2 font-body-sm text-sm font-medium text-on-surface shadow-xs hover:bg-surface-container-high transition-colors"
          >
            <span className="material-symbols-outlined text-[18px] text-outline">group</span>
            <span>Customers</span>
          </Link>
          {canCreate && (
            <button
              onClick={() => setIsCreateOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 font-body-sm text-sm font-semibold text-on-primary shadow-sm hover:bg-primary-container active:scale-[0.99] transition-all"
            >
              <span className="material-symbols-outlined text-[18px]">add_circle</span>
              <span>Record Receipt</span>
            </button>
          )}
        </div>
      </div>

      {/* Staff Notice */}
      {isStaff && (
        <div className="rounded-xl border border-secondary/20 bg-surface-container-low p-4 text-xs text-on-surface flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-secondary/10 text-secondary flex items-center justify-center shrink-0">
            <span className="material-symbols-outlined text-[16px]">info</span>
          </div>
          <div>
            <span className="font-semibold text-on-surface">Staff Permissions:</span>{" "}
            <span className="text-on-surface-variant">
              You have permission to record new payments and view receipt records. Voiding requires Owner authority and corrections require Manager authority.
            </span>
          </div>
        </div>
      )}

      {/* Operational Scope Notice */}
      <div className="rounded-xl border border-secondary/20 bg-surface-container-low p-4 text-xs text-on-surface flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0">
            <span className="material-symbols-outlined text-[16px]">receipt_long</span>
          </div>
          <div>
            <span className="font-semibold text-on-surface">Operational Receipt Tracking:</span>{" "}
            <span className="text-on-surface-variant">
              Records payments as you report them. BizPilot does not verify bank settlement and is not a reconciliation tool.
            </span>
          </div>
        </div>
      </div>

      {/* Customer / Order Filter Banner */}
      {(selectedCustomerId || selectedOrderId) && (
        <div className="flex items-center justify-between rounded-xl border border-primary/20 bg-surface-container-low px-4 py-3 text-xs text-on-surface">
          <span className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary text-[18px]">filter_alt</span>
            {selectedOrderId && <>Filtering receipts for order: <strong className="font-mono text-primary">{selectedOrderId}</strong> </>}
            {selectedCustomerId && <>Filtering receipts for customer: <strong className="font-mono text-primary">{selectedCustomerId}</strong></>}
          </span>
          <Link href={`/workspace/${orgId}/payments`} className="font-medium text-primary hover:underline ml-2">
            Show All Payments
          </Link>
        </div>
      )}

      {/* KPI Metrics Strip */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {/* Total Collected Today */}
        <div className="bg-surface-container-lowest p-5 rounded-xl shadow-xs border border-surface-container-high/60 flex flex-col justify-between relative overflow-hidden group">
          <div className="flex items-center justify-between mb-2">
            <span className="font-label-caps text-xs uppercase text-on-surface-variant tracking-wider">
              Today's Collections ({todayStr})
            </span>
            <div className="w-8 h-8 rounded-lg bg-surface-container-high flex items-center justify-center text-primary">
              <span className="material-symbols-outlined text-[18px]">payments</span>
            </div>
          </div>
          <div className="mt-2 mb-1">
            <div className="font-data-metric text-2xl font-bold text-on-surface tracking-tight">
              {dailyTotalData
                ? formatMoney(dailyTotalData.total_minor, dailyTotalData.currency_code)
                : "Rs. 0.00"}
            </div>
          </div>
          <div className="flex items-center justify-between text-xs text-on-surface-variant pt-2 border-t border-surface-container-low">
            <span className="flex items-center gap-1 text-tertiary font-data-badge font-semibold">
              <span className="material-symbols-outlined text-[14px]">check_circle</span>{" "}
              {dailyTotalData ? dailyTotalData.payment_count : 0} active receipt(s) collected today
            </span>
          </div>
        </div>

      </div>

      {/* Filter Tabs & Channel Selector */}
      <div className="bg-surface-container-lowest p-4 rounded-xl shadow-xs border border-surface-container-high/60 flex flex-col sm:flex-row gap-4 sm:items-center sm:justify-between">
        {/* Status Tabs */}
        <div className="flex items-center p-1 rounded-lg bg-surface-container-low border border-surface-container-high/60 overflow-x-auto">
          {(["all", "active", "voided", "corrected"] as const).map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`rounded-md px-3 py-1.5 text-xs font-semibold capitalize transition-all ${
                statusFilter === st
                  ? "bg-surface-container-lowest text-primary shadow-xs"
                  : "text-on-surface-variant hover:text-on-surface"
              }`}
            >
              {st}
            </button>
          ))}
        </div>

        {/* Channel Dropdown */}
        <div className="flex items-center gap-2">
          <label className="text-xs font-semibold uppercase font-label-caps text-on-surface-variant tracking-wider">
            Channel:
          </label>
          <select
            value={channelFilter}
            onChange={(e) => setChannelFilter(e.target.value)}
            className="rounded-lg border border-outline-variant/40 bg-surface-container-lowest px-3 py-1.5 font-body-sm text-xs text-on-surface focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/10 shadow-xs transition-all"
          >
            <option value="all">All Channels</option>
            <option value="cash">Cash</option>
            <option value="bank_transfer">Bank Transfer</option>
            <option value="cheque">Cheque</option>
            <option value="mobile_wallet">Mobile Wallet</option>
            <option value="other">Other</option>
          </select>
        </div>
      </div>

      {/* Payments Table */}
      <div className="overflow-hidden rounded-xl border border-surface-container-high/60 bg-surface-container-lowest shadow-xs">
        {isLoading ? (
          <div className="p-8 text-center text-sm text-on-surface-variant">
            Loading payments...
          </div>
        ) : error ? (
          <div className="p-8 text-center text-sm text-error">
            Failed to load payments: {error.message}
            <div className="mt-2">
              <button
                onClick={() => refetch()}
                className="text-xs text-primary underline font-medium hover:text-primary-container"
              >
                Retry
              </button>
            </div>
          </div>
        ) : payments.length === 0 ? (
          <div className="p-8 text-center text-sm text-on-surface-variant">
            No payments found. {canCreate && "Click 'Record Receipt' to log your first payment."}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-surface-container-low text-on-surface-variant font-label-caps text-xs uppercase h-10 select-none border-b border-surface-container-high/60">
                  <th className="px-4 py-3 font-semibold">Receipt #</th>
                  <th className="px-4 py-3 font-semibold">Channel</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3 font-semibold">Date</th>
                  <th className="px-4 py-3 text-right font-semibold">Amount</th>
                  <th className="px-4 py-3 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-container-low font-body-md text-sm text-on-surface">
                {payments.map((payment) => (
                  <tr key={payment.id} className="hover:bg-surface-container-low/60 transition-colors group">
                    <td className="px-4 py-3.5 font-semibold text-on-surface font-mono font-data-cell">
                      {payment.payment_number}
                    </td>
                    <td className="px-4 py-3.5 text-on-surface">
                      <div className="font-medium text-xs text-on-surface">
                        {formatChannel(payment.channel)}
                      </div>
                      {payment.account_label && (
                        <div className="text-[11px] text-on-surface-variant">
                          {payment.account_label}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3.5">
                      <span
                        className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-data-badge text-xs font-semibold capitalize ${
                          payment.status === "active"
                            ? "bg-tertiary-container/15 text-tertiary"
                            : payment.status === "voided"
                            ? "bg-error-container text-on-error-container"
                            : "bg-secondary-fixed text-on-secondary-fixed"
                        }`}
                      >
                        <span
                          className={`w-1.5 h-1.5 rounded-full ${
                            payment.status === "active"
                              ? "bg-tertiary"
                              : payment.status === "voided"
                              ? "bg-error"
                              : "bg-secondary"
                          }`}
                        ></span>
                        {payment.status}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 text-on-surface-variant font-data-cell text-xs">
                      {new Date(payment.received_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3.5 text-right font-semibold text-on-surface font-data-cell">
                      {formatMoney(payment.amount_minor, payment.currency_code)}
                    </td>
                    <td className="px-4 py-3.5 text-right space-x-2">
                      <button
                        onClick={() => handleOpenDetail(payment)}
                        className="text-xs text-primary hover:text-primary-container font-medium transition-colors"
                      >
                        View
                      </button>

                      {payment.status === "active" && canCorrect && (
                        <button
                          onClick={() => handleOpenCorrect(payment)}
                          className="text-xs text-secondary hover:text-secondary-container font-medium transition-colors"
                        >
                          Correct
                        </button>
                      )}

                      {payment.status === "active" && canVoid && (
                        <button
                          onClick={() => handleOpenVoid(payment)}
                          className="text-xs text-error hover:text-on-error-container font-medium transition-colors"
                        >
                          Void
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modals */}
      <PaymentCreateModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        orgId={orgId}
        token={token}
        initialOrderId={selectedOrderId}
        initialCustomerId={selectedCustomerId}
      />

      <PaymentDetailModal
        isOpen={isDetailOpen}
        onClose={() => {
          setIsDetailOpen(false);
          setSelectedPayment(null);
        }}
        payment={selectedPayment}
      />

      <PaymentVoidModal
        isOpen={isVoidOpen}
        onClose={() => {
          setIsVoidOpen(false);
          setSelectedPayment(null);
        }}
        payment={selectedPayment}
        orgId={orgId}
        token={token}
      />

      <PaymentCorrectModal
        isOpen={isCorrectOpen}
        onClose={() => {
          setIsCorrectOpen(false);
          setSelectedPayment(null);
        }}
        payment={selectedPayment}
        orgId={orgId}
        token={token}
      />
    </div>
  );
}
